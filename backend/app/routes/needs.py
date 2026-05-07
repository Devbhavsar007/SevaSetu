from __future__ import annotations

"""
Need (community request) routes — full CRUD with filtering, pagination, and audit.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func

from ..database import get_db
from ..models import User, Need, Volunteer, Assignment, AuditLog
from ..schemas import (
    NeedCreateRequest, NeedUpdateRequest, NeedResponse, NeedBriefResponse,
    NeedStatus, NeedCategory, MessageResponse,
)
from ..middleware.auth import get_current_user, get_current_admin, get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/needs", tags=["Needs"])


def _need_to_response(need: Need, db: Session) -> NeedResponse:
    """Convert Need model to response schema with joined data."""
    reporter_name = None
    if need.reported_by:
        reporter = db.query(User).filter(User.id == need.reported_by).first()
        reporter_name = reporter.name if reporter else None

    assigned_vol_name = None
    if need.assigned_volunteer_id:
        vol = db.query(Volunteer).filter(Volunteer.id == need.assigned_volunteer_id).first()
        if vol:
            user = db.query(User).filter(User.id == vol.user_id).first()
            assigned_vol_name = user.name if user else None

    images = []
    try:
        images = json.loads(need.images) if need.images else []
    except (json.JSONDecodeError, TypeError):
        pass

    return NeedResponse(
        id=need.id,
        reported_by=need.reported_by,
        reporter_name=reporter_name,
        title=need.title,
        description=need.description,
        category=need.category,
        urgency=need.urgency,
        status=need.status,
        latitude=need.latitude,
        longitude=need.longitude,
        address=need.address,
        people_affected=need.people_affected,
        source=need.source,
        ocr_raw_text=need.ocr_raw_text,
        images=images,
        assigned_volunteer_id=need.assigned_volunteer_id,
        assigned_volunteer_name=assigned_vol_name,
        verification_status=need.verification_status,
        notes=need.notes,
        created_at=need.created_at,
        updated_at=need.updated_at,
        resolved_at=need.resolved_at,
    )


@router.post("/", response_model=NeedResponse, status_code=status.HTTP_201_CREATED)
async def create_need(
    body: NeedCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new community need / request."""
    final_lat = body.latitude
    final_lon = body.longitude

    # Auto-geocode if coordinates are missing/default (0,0)
    if (final_lat == 0.0 and final_lon == 0.0) and body.address and len(body.address.strip()) >= 3:
        from ..services.geo_service import geocode_address
        coords = geocode_address(body.address)
        if coords:
            final_lat, final_lon = coords
            logger.info(f"Auto-geocoded need address '{body.address}' -> ({final_lat}, {final_lon})")

    need = Need(
        reported_by=current_user.id,
        title=body.title,
        description=body.description,
        category=body.category.value,
        urgency=body.urgency,
        latitude=final_lat,
        longitude=final_lon,
        address=body.address,
        people_affected=body.people_affected,
        source=body.source.value,
        ocr_raw_text=body.ocr_raw_text,
        notes=body.notes,
    )
    db.add(need)

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="need.created",
        entity_type="need",
        entity_id=need.id,
        details=json.dumps({
            "category": body.category.value,
            "urgency": body.urgency,
            "source": body.source.value,
        }),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(need)

    logger.info(f"Need created: '{need.title}' [{need.category}] urgency={need.urgency} by {current_user.name}")

    # NEW: Emit WebSocket event for real-time updates
    try:
        from .realtime import emit_event
        await emit_event("need.created", {
            "id": need.id, "title": need.title, "category": need.category,
            "urgency": need.urgency, "status": need.status,
            "latitude": need.latitude, "longitude": need.longitude,
            "people_affected": need.people_affected,
        }, room="admin")
    except Exception as e:
        logger.warning(f"WS emit failed for need.created: {e}")

    return _need_to_response(need, db)


@router.get("/", response_model=List[NeedResponse])
async def list_needs(
    category: Optional[NeedCategory] = Query(default=None, description="Filter by category"),
    status_filter: Optional[NeedStatus] = Query(default=None, alias="status", description="Filter by status"),
    urgency_min: Optional[int] = Query(default=None, ge=1, le=5, description="Minimum urgency"),
    urgency_max: Optional[int] = Query(default=None, ge=1, le=5, description="Maximum urgency"),
    search: Optional[str] = Query(default=None, max_length=200, description="Search in title/description"),
    sort_by: Optional[str] = Query(default="created_at", description="Sort field"),
    sort_order: Optional[str] = Query(default="desc", description="Sort order: asc or desc"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List needs with comprehensive filtering, search, and pagination.
    """
    query = db.query(Need)

    # Apply filters
    if category:
        query = query.filter(Need.category == category.value)
    if status_filter:
        query = query.filter(Need.status == status_filter.value)
    if urgency_min:
        query = query.filter(Need.urgency >= urgency_min)
    if urgency_max:
        query = query.filter(Need.urgency <= urgency_max)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Need.title.ilike(search_term)) | (Need.description.ilike(search_term))
        )

    # Sort
    sort_column = getattr(Need, sort_by, Need.created_at)
    if sort_order == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    # Paginate
    offset = (page - 1) * per_page
    needs = query.offset(offset).limit(per_page).all()

    return [_need_to_response(n, db) for n in needs]


@router.get("/map/", response_model=List[NeedBriefResponse])
async def list_needs_for_map(
    category: Optional[NeedCategory] = Query(default=None),
    status_filter: Optional[NeedStatus] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lightweight endpoint for map markers — returns only essential fields.
    No pagination, returns all for map rendering.
    """
    query = db.query(Need).filter(Need.status.in_(["open", "assigned", "in_progress"]))

    if category:
        query = query.filter(Need.category == category.value)
    if status_filter:
        query = query.filter(Need.status == status_filter.value)

    needs = query.all()
    return [NeedBriefResponse.model_validate(n) for n in needs]


@router.get("/categories/")
async def get_categories():
    """Return all valid need categories with descriptions."""
    return {
        "categories": [
            {"value": "medical", "label": "Medical", "icon": "❤️‍🩹", "color": "#EF4444"},
            {"value": "food", "label": "Food", "icon": "🍚", "color": "#F97316"},
            {"value": "shelter", "label": "Shelter", "icon": "🏠", "color": "#3B82F6"},
            {"value": "rescue", "label": "Rescue", "icon": "🚨", "color": "#A855F7"},
            {"value": "education", "label": "Education", "icon": "📚", "color": "#10B981"},
            {"value": "clothing", "label": "Clothing", "icon": "👕", "color": "#EAB308"},
            {"value": "sanitation", "label": "Sanitation", "icon": "🧹", "color": "#14B8A6"},
            {"value": "water", "label": "Water", "icon": "💧", "color": "#06B6D4"},
            {"value": "other", "label": "Other", "icon": "📋", "color": "#6B7280"},
        ]
    }


@router.get("/{need_id}/", response_model=NeedResponse)
async def get_need(
    need_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single need by ID with full details."""
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")
    return _need_to_response(need, db)


@router.patch("/{need_id}/", response_model=NeedResponse)
async def update_need(
    need_id: str,
    body: NeedUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a need. Admin can update any, volunteers can only update their own."""
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    # Permission check
    if current_user.role != "admin" and need.reported_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit needs you reported")

    # Track changes for audit
    changes = {}
    update_data = body.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        old_value = getattr(need, field)
        if hasattr(value, 'value'):  # Handle enums
            value = value.value
        if old_value != value:
            changes[field] = {"old": str(old_value), "new": str(value)}
            setattr(need, field, value)

    # Handle status transitions
    if body.status:
        new_status = body.status.value
        valid_transitions = {
            "open": ["assigned", "cancelled"],
            "assigned": ["in_progress", "open", "cancelled"],
            "in_progress": ["resolved", "assigned", "cancelled"],
            "resolved": ["open"],  # Reopen
            "cancelled": ["open"],  # Reactivate
        }
        allowed = valid_transitions.get(need.status, [])
        if new_status not in allowed and current_user.role != "admin":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from '{need.status}' to '{new_status}'. Allowed: {allowed}"
            )

        if new_status == "resolved":
            need.resolved_at = datetime.now(timezone.utc)
        elif new_status == "open":
            need.resolved_at = None

    need.updated_at = datetime.now(timezone.utc)

    # Audit
    if changes:
        audit = AuditLog(
            user_id=current_user.id,
            action="need.updated",
            entity_type="need",
            entity_id=need.id,
            details=json.dumps(changes),
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)

    db.commit()
    db.refresh(need)

    # NEW: Emit WebSocket event for real-time updates
    try:
        from .realtime import emit_event
        await emit_event("need.updated", {
            "id": need.id, "title": need.title, "category": need.category,
            "urgency": need.urgency, "status": need.status,
            "changes": changes,
        }, room="admin")
    except Exception as e:
        logger.warning(f"WS emit failed for need.updated: {e}")

    return _need_to_response(need, db)


@router.delete("/{need_id}/", response_model=MessageResponse)
async def delete_need(
    need_id: str,
    request: Request,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete a need. Admin only."""
    need = db.query(Need).filter(Need.id == need_id).first()
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    # Audit before deletion
    audit = AuditLog(
        user_id=current_user.id,
        action="need.deleted",
        entity_type="need",
        entity_id=need.id,
        details=json.dumps({"title": need.title, "category": need.category}),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)

    db.delete(need)
    db.commit()

    return MessageResponse(message=f"Need '{need.title}' deleted successfully")
