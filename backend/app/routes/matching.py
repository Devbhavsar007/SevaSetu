from __future__ import annotations

"""
Matching routes — Smart volunteer-to-need matching and assignment management.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import User, Need, Volunteer, Assignment, AuditLog
from ..schemas import (
    AssignmentCreateRequest, AssignmentStatusUpdate, AssignmentResponse,
    MatchSuggestionsResponse, MatchSuggestion, VolunteerBriefResponse,
    MessageResponse,
)
from ..middleware.auth import get_current_user, get_current_admin
from ..services.matching_engine import find_best_matches, calculate_match_score
from ..services.geo_service import haversine_distance
from ..services import fcm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matching", tags=["Matching & Assignments"])


@router.get("/suggest/{need_id}/", response_model=MatchSuggestionsResponse)
async def get_match_suggestions(
    need_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the top volunteer matches for a specific need.
    Uses the smart matching algorithm (distance + skills + availability).
    """
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    matches = find_best_matches(db, need, limit=limit)

    # Count total available volunteers for context
    total_available = db.query(Volunteer).filter(
        Volunteer.availability == "available",
        Volunteer.latitude.isnot(None),
    ).count()

    suggestions = []
    for m in matches:
        suggestions.append(MatchSuggestion(
            volunteer=VolunteerBriefResponse(
                id=m["volunteer_id"],
                user_name=m["user_name"],
                skills=m["skills"],
                latitude=m["latitude"],
                longitude=m["longitude"],
                availability=m["availability"],
                has_vehicle=m["has_vehicle"],
                tasks_completed=m["tasks_completed"],
                rating=m["rating"],
            ),
            match_score=m["match_score"],
            distance_km=m["distance_km"],
            skill_match_pct=m["skill_match_pct"],
            reasons=m["reasons"],
        ))

    return MatchSuggestionsResponse(
        need_id=need.id,
        need_title=need.title,
        need_category=need.category,
        suggestions=suggestions,
        total_available=total_available,
    )


@router.post("/assign/", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: AssignmentCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Assign a volunteer to a need. Creates an assignment record and updates statuses.
    Admin or the need reporter can create assignments.
    """
    # Validate need
    need = db.query(Need).filter(Need.id == body.need_id).first()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    if need.status not in ("open", "assigned"):
        raise HTTPException(status_code=400, detail=f"Need is '{need.status}', cannot assign new volunteers")

    # Validate volunteer
    vol = db.query(Volunteer).filter(Volunteer.id == body.volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    if vol.availability != "available":
        raise HTTPException(status_code=400, detail=f"Volunteer is '{vol.availability}', not available for assignment")

    # Check for duplicate active assignment
    existing = db.query(Assignment).filter(
        Assignment.need_id == body.need_id,
        Assignment.volunteer_id == body.volunteer_id,
        Assignment.status.in_(["assigned", "accepted", "in_progress"]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Volunteer is already assigned to this need")

    # Calculate match score and distance
    distance_km = 0.0
    match_score = 0.0
    if vol.latitude and vol.longitude:
        distance_km = haversine_distance(need.latitude, need.longitude, vol.latitude, vol.longitude)
        match_data = calculate_match_score(vol, need, distance_km)
        match_score = match_data["total_score"]

    # Create assignment
    assignment = Assignment(
        need_id=need.id,
        volunteer_id=vol.id,
        match_score=match_score,
        distance_km=round(distance_km, 2),
        admin_notes=body.admin_notes,
    )
    db.add(assignment)

    # Update need status
    need.status = "assigned"
    need.assigned_volunteer_id = vol.id
    need.updated_at = datetime.now(timezone.utc)

    # Update volunteer status
    vol.availability = "busy"
    vol.current_task_id = assignment.id
    vol.updated_at = datetime.now(timezone.utc)

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="assignment.created",
        entity_type="assignment",
        entity_id=assignment.id,
        details=json.dumps({
            "need_id": need.id,
            "volunteer_id": vol.id,
            "match_score": match_score,
            "distance_km": round(distance_km, 2),
        }),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)

    # Send push notification to volunteer
    if vol.fcm_token:
        await fcm_service.send_task_assigned_notification(
            fcm_token=vol.fcm_token,
            need_title=need.title,
            need_category=need.category,
            distance_km=distance_km,
            assignment_id=assignment.id,
        )

    # Build response
    user = db.query(User).filter(User.id == vol.user_id).first()

    # NEW: Emit WebSocket event for real-time updates
    try:
        from .realtime import emit_event
        await emit_event("assignment.created", {
            "id": assignment.id, "need_id": need.id,
            "volunteer_id": vol.id, "need_title": need.title,
            "volunteer_name": user.name if user else "Unknown",
            "match_score": match_score,
        }, room="admin")
    except Exception as e:
        logger.warning(f"WS emit failed for assignment.created: {e}")

    return AssignmentResponse(
        id=assignment.id,
        need_id=assignment.need_id,
        volunteer_id=assignment.volunteer_id,
        status=assignment.status,
        match_score=assignment.match_score,
        distance_km=assignment.distance_km,
        assigned_at=assignment.assigned_at,
        need_title=need.title,
        need_category=need.category,
        volunteer_name=user.name if user else None,
        admin_notes=assignment.admin_notes,
    )


@router.patch("/assignment/{assignment_id}/status/", response_model=AssignmentResponse)
async def update_assignment_status(
    assignment_id: str,
    body: AssignmentStatusUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update assignment status through the lifecycle:
    assigned → accepted → in_progress → completed
    or assigned → rejected
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    vol = db.query(Volunteer).filter(Volunteer.id == assignment.volunteer_id).first()
    need = db.query(Need).filter(Need.id == assignment.need_id).first()

    # Permission: volunteer can only update their own assignments
    if current_user.role != "admin":
        if not vol or vol.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Can only update your own assignment")

    # Validate status transition
    new_status = body.status.value
    valid_transitions = {
        "assigned": ["accepted", "rejected"],
        "accepted": ["in_progress", "rejected"],
        "in_progress": ["completed"],
        "completed": [],
        "rejected": [],
    }
    allowed = valid_transitions.get(assignment.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{assignment.status}' to '{new_status}'. Allowed: {allowed}"
        )

    old_status = assignment.status
    assignment.status = new_status

    now = datetime.now(timezone.utc)

    if new_status == "accepted":
        assignment.accepted_at = now
    elif new_status == "in_progress":
        assignment.started_at = now
        if need:
            need.status = "in_progress"
    elif new_status == "completed":
        assignment.completed_at = now
        assignment.feedback = body.feedback
        assignment.rating = body.rating

        # Update volunteer stats
        if vol:
            vol.tasks_completed += 1
            vol.availability = "available"
            vol.current_task_id = None
            if body.rating:
                vol.update_rating(body.rating)

        # Update need status
        if need:
            need.status = "resolved"
            need.resolved_at = now

    elif new_status == "rejected":
        assignment.rejection_reason = body.rejection_reason

        # Free up the volunteer
        if vol:
            vol.availability = "available"
            vol.current_task_id = None

        # Reopen the need
        if need:
            need.status = "open"
            need.assigned_volunteer_id = None

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action=f"assignment.{new_status}",
        entity_type="assignment",
        entity_id=assignment.id,
        details=json.dumps({
            "old_status": old_status,
            "new_status": new_status,
            "rejection_reason": body.rejection_reason,
        }),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)

    user = db.query(User).filter(User.id == vol.user_id).first() if vol else None
    return AssignmentResponse(
        id=assignment.id,
        need_id=assignment.need_id,
        volunteer_id=assignment.volunteer_id,
        status=assignment.status,
        match_score=assignment.match_score,
        distance_km=assignment.distance_km,
        assigned_at=assignment.assigned_at,
        accepted_at=assignment.accepted_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
        rejection_reason=assignment.rejection_reason,
        feedback=assignment.feedback,
        rating=assignment.rating,
        admin_notes=assignment.admin_notes,
        need_title=need.title if need else None,
        need_category=need.category if need else None,
        volunteer_name=user.name if user else None,
    )


@router.get("/assignment/{assignment_id}/", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get assignment details."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    vol = db.query(Volunteer).filter(Volunteer.id == assignment.volunteer_id).first()
    need = db.query(Need).filter(Need.id == assignment.need_id).first()
    user = db.query(User).filter(User.id == vol.user_id).first() if vol else None

    return AssignmentResponse(
        id=assignment.id,
        need_id=assignment.need_id,
        volunteer_id=assignment.volunteer_id,
        status=assignment.status,
        match_score=assignment.match_score,
        distance_km=assignment.distance_km,
        assigned_at=assignment.assigned_at,
        accepted_at=assignment.accepted_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
        rejection_reason=assignment.rejection_reason,
        feedback=assignment.feedback,
        rating=assignment.rating,
        admin_notes=assignment.admin_notes,
        need_title=need.title if need else None,
        need_category=need.category if need else None,
        volunteer_name=user.name if user else None,
    )


@router.get("/assignments/", response_model=List[AssignmentResponse])
async def list_assignments(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    need_id: Optional[str] = Query(default=None),
    volunteer_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """List all assignments with filters. Admin only."""
    query = db.query(Assignment)

    if status_filter:
        query = query.filter(Assignment.status == status_filter)
    if need_id:
        query = query.filter(Assignment.need_id == need_id)
    if volunteer_id:
        query = query.filter(Assignment.volunteer_id == volunteer_id)

    query = query.order_by(desc(Assignment.assigned_at))
    offset = (page - 1) * per_page
    assignments = query.offset(offset).limit(per_page).all()

    results = []
    for a in assignments:
        vol = db.query(Volunteer).filter(Volunteer.id == a.volunteer_id).first()
        need = db.query(Need).filter(Need.id == a.need_id).first()
        user = db.query(User).filter(User.id == vol.user_id).first() if vol else None

        results.append(AssignmentResponse(
            id=a.id,
            need_id=a.need_id,
            volunteer_id=a.volunteer_id,
            status=a.status,
            match_score=a.match_score,
            distance_km=a.distance_km,
            assigned_at=a.assigned_at,
            accepted_at=a.accepted_at,
            started_at=a.started_at,
            completed_at=a.completed_at,
            rejection_reason=a.rejection_reason,
            feedback=a.feedback,
            rating=a.rating,
            admin_notes=a.admin_notes,
            need_title=need.title if need else None,
            need_category=need.category if need else None,
            volunteer_name=user.name if user else None,
        ))

    return results
