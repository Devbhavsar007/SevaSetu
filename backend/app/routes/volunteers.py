from __future__ import annotations

"""
Volunteer routes — profile management, location, availability, task history.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import User, Volunteer, Assignment, Need, AuditLog
from ..schemas import (
    VolunteerCreateRequest, VolunteerUpdateRequest,
    VolunteerLocationUpdate, VolunteerAvailabilityUpdate, VolunteerFCMUpdate,
    VolunteerResponse, VolunteerBriefResponse,
    AssignmentResponse, MessageResponse, VolunteerAvailability,
    SOSRequest, SkillVerifyRequest,
)
from ..middleware.auth import get_current_user, get_current_admin
from ..services.geo_service import haversine_distance, bounding_box

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/volunteers", tags=["Volunteers"])


def _vol_to_response(vol: Volunteer, db: Session) -> VolunteerResponse:
    """Build full volunteer response with user info."""
    user = db.query(User).filter(User.id == vol.user_id).first()
    return VolunteerResponse(
        id=vol.id,
        user_id=vol.user_id,
        phone=vol.phone,
        skills=vol.skills_list,
        has_vehicle=vol.has_vehicle,
        vehicle_type=vol.vehicle_type,
        latitude=vol.latitude,
        longitude=vol.longitude,
        address=vol.address,
        availability=vol.availability,
        current_task_id=vol.current_task_id,
        tasks_completed=vol.tasks_completed,
        rating=vol.rating,
        total_ratings=vol.total_ratings,
        created_at=vol.created_at,
        updated_at=vol.updated_at,
        user_name=user.name if user else None,
        user_email=user.email if user else None,
        user_picture=user.picture if user else None,
    )


@router.post("/setup/", response_model=VolunteerResponse, status_code=status.HTTP_201_CREATED)
async def setup_volunteer_profile(
    body: VolunteerCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set up or update a volunteer's profile (skills, vehicle, location).
    Called after first login to complete the profile.
    """
    vol = db.query(Volunteer).filter(Volunteer.user_id == current_user.id).first()

    if vol is None:
        # Create new profile
        vol = Volunteer(user_id=current_user.id)
        db.add(vol)

    # Update fields
    vol.phone = body.phone or vol.phone
    if body.skills:
        vol.skills_list = body.skills
    vol.has_vehicle = body.has_vehicle
    vol.vehicle_type = body.vehicle_type.value if body.vehicle_type else None
    if body.latitude is not None:
        vol.latitude = body.latitude
    if body.longitude is not None:
        vol.longitude = body.longitude
    vol.address = body.address or vol.address
    vol.updated_at = datetime.now(timezone.utc)

    # Auto-geocode address if coordinates are missing/default
    if (vol.latitude is None or vol.longitude is None or
        (vol.latitude == 0.0 and vol.longitude == 0.0)):
        address_to_geocode = vol.address
        if address_to_geocode and len(address_to_geocode.strip()) >= 3:
            from ..services.geo_service import geocode_address
            coords = geocode_address(address_to_geocode)
            if coords:
                vol.latitude, vol.longitude = coords
                logger.info(f"Auto-geocoded volunteer address '{address_to_geocode}' -> ({vol.latitude}, {vol.longitude})")

    # Ensure user role is set
    if current_user.role != "volunteer":
        current_user.role = "volunteer"

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="volunteer.profile_setup",
        entity_type="volunteer",
        entity_id=vol.id,
        details=json.dumps({"skills": body.skills, "has_vehicle": body.has_vehicle}),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(vol)

    return _vol_to_response(vol, db)


@router.get("/", response_model=List[VolunteerResponse])
async def list_volunteers(
    availability: Optional[VolunteerAvailability] = Query(default=None),
    skill: Optional[str] = Query(default=None, description="Filter by skill"),
    has_vehicle: Optional[bool] = Query(default=None),
    near_lat: Optional[float] = Query(default=None, ge=-90, le=90, description="Center latitude for proximity search"),
    near_lon: Optional[float] = Query(default=None, ge=-180, le=180, description="Center longitude for proximity search"),
    radius_km: float = Query(default=10.0, ge=0.5, le=100, description="Search radius in km"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List volunteers with filtering by availability, skills, vehicle, and proximity.
    """
    query = db.query(Volunteer)

    if availability:
        query = query.filter(Volunteer.availability == availability.value)
    if has_vehicle is not None:
        query = query.filter(Volunteer.has_vehicle == has_vehicle)
    if skill:
        # SQLite JSON search — look for skill in the skills text column
        query = query.filter(Volunteer.skills.ilike(f'%"{skill.lower()}"%'))

    # Proximity filter using bounding box
    if near_lat is not None and near_lon is not None:
        min_lat, max_lat, min_lon, max_lon = bounding_box(near_lat, near_lon, radius_km)
        query = query.filter(
            Volunteer.latitude.isnot(None),
            Volunteer.longitude.isnot(None),
            Volunteer.latitude.between(min_lat, max_lat),
            Volunteer.longitude.between(min_lon, max_lon),
        )

    # Paginate
    offset = (page - 1) * per_page
    volunteers = query.offset(offset).limit(per_page).all()

    # Post-filter by exact radius if proximity search
    if near_lat is not None and near_lon is not None:
        volunteers = [
            v for v in volunteers
            if haversine_distance(near_lat, near_lon, v.latitude, v.longitude) <= radius_km
        ]

    return [_vol_to_response(v, db) for v in volunteers]


@router.get("/map/", response_model=List[VolunteerBriefResponse])
async def list_volunteers_for_map(
    availability: Optional[VolunteerAvailability] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Lightweight response for map markers. Admin only."""
    query = db.query(Volunteer).filter(
        Volunteer.latitude.isnot(None),
        Volunteer.longitude.isnot(None),
    )
    if availability:
        query = query.filter(Volunteer.availability == availability.value)

    volunteers = query.all()
    results = []
    for v in volunteers:
        user = db.query(User).filter(User.id == v.user_id).first()
        results.append(VolunteerBriefResponse(
            id=v.id,
            user_name=user.name if user else "Unknown",
            skills=v.skills_list,
            latitude=v.latitude,
            longitude=v.longitude,
            availability=v.availability,
            has_vehicle=v.has_vehicle,
            tasks_completed=v.tasks_completed,
            rating=v.rating,
        ))
    return results


@router.get("/me/", response_model=VolunteerResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current volunteer's own profile."""
    vol = db.query(Volunteer).filter(Volunteer.user_id == current_user.id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer profile not set up. Call POST /volunteers/setup first.")
    return _vol_to_response(vol, db)


@router.get("/{volunteer_id}/", response_model=VolunteerResponse)
async def get_volunteer(
    volunteer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a volunteer by ID."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    return _vol_to_response(vol, db)


@router.patch("/{volunteer_id}/", response_model=VolunteerResponse)
async def update_volunteer(
    volunteer_id: str,
    body: VolunteerUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update volunteer profile. Volunteers can only update their own."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    if current_user.role != "admin" and vol.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update your own profile")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "skills" and value is not None:
            vol.skills_list = value
        elif field == "vehicle_type" and value is not None:
            vol.vehicle_type = value.value if hasattr(value, 'value') else value
        elif value is not None:
            setattr(vol, field, value)

    vol.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vol)

    return _vol_to_response(vol, db)


@router.patch("/{volunteer_id}/location/", response_model=MessageResponse)
async def update_location(
    volunteer_id: str,
    body: VolunteerLocationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update volunteer's GPS location. Called periodically from mobile app."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    if vol.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot update another volunteer's location")

    vol.latitude = body.latitude
    vol.longitude = body.longitude
    if body.address:
        vol.address = body.address
    vol.updated_at = datetime.now(timezone.utc)

    db.commit()
    return MessageResponse(message="Location updated")


@router.patch("/{volunteer_id}/availability/", response_model=MessageResponse)
async def update_availability(
    volunteer_id: str,
    body: VolunteerAvailabilityUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update volunteer's availability status."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    if vol.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot update another volunteer's availability")

    old_status = vol.availability
    vol.availability = body.availability.value
    vol.updated_at = datetime.now(timezone.utc)

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="volunteer.availability_changed",
        entity_type="volunteer",
        entity_id=vol.id,
        details=json.dumps({"old": old_status, "new": body.availability.value}),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    # NEW: Emit WebSocket event for real-time updates
    try:
        from .realtime import emit_event
        await emit_event("volunteer.updated", {
            "id": vol.id, "availability": body.availability.value,
            "old_availability": old_status,
        }, room="admin")
    except Exception as e:
        logger.warning(f"WS emit failed for volunteer.updated: {e}")

    return MessageResponse(message=f"Availability changed: {old_status} → {body.availability.value}")


@router.patch("/{volunteer_id}/fcm-token/", response_model=MessageResponse)
async def update_fcm_token(
    volunteer_id: str,
    body: VolunteerFCMUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update volunteer's FCM push notification token."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    if vol.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot update another volunteer's FCM token")

    vol.fcm_token = body.fcm_token
    vol.updated_at = datetime.now(timezone.utc)
    db.commit()

    return MessageResponse(message="FCM token updated")


@router.get("/{volunteer_id}/tasks/", response_model=List[AssignmentResponse])
async def get_volunteer_tasks(
    volunteer_id: str,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a volunteer's assignment history."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    # Volunteers can only see their own tasks, admins can see anyone's
    if vol.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(Assignment).filter(Assignment.volunteer_id == volunteer_id)

    if status_filter:
        query = query.filter(Assignment.status == status_filter)

    query = query.order_by(desc(Assignment.assigned_at))

    offset = (page - 1) * per_page
    assignments = query.offset(offset).limit(per_page).all()

    results = []
    for a in assignments:
        need = db.query(Need).filter(Need.id == a.need_id).first()
        user = db.query(User).filter(User.id == vol.user_id).first()
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


# ============================================================
# SOS PANIC BUTTON (Task 2.5)
# ============================================================

@router.post("/sos/", status_code=status.HTTP_201_CREATED)
async def trigger_sos(
    body: SOSRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SOS — Emergency panic button for volunteers."""
    from ..schemas import SOSResponse

    need = Need(
        reported_by=current_user.id,
        title=f"\U0001f198 SOS \u2014 {current_user.name} needs immediate help",
        description=body.message,
        category="rescue",
        urgency=5,
        latitude=body.latitude,
        longitude=body.longitude,
        people_affected=1,
        source="sos",
        status="open",
    )
    db.add(need)

    audit = AuditLog(
        user_id=current_user.id,
        action="sos.triggered",
        entity_type="need",
        entity_id=need.id,
        details=json.dumps({"lat": body.latitude, "lon": body.longitude, "message": body.message}),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(need)

    try:
        from .realtime import emit_event
        await emit_event("sos.triggered", {
            "id": need.id, "user_name": current_user.name,
            "latitude": body.latitude, "longitude": body.longitude,
            "message": body.message,
        }, room="admin")
    except Exception as e:
        logger.warning(f"WS emit failed for sos.triggered: {e}")

    return SOSResponse(
        sos_id=need.id, need_id=need.id,
        message="SOS sent \u2014 Help is on the way",
        estimated_response_time="~15 minutes",
    )


# ============================================================
# FATIGUE SCORE (Task 2.2)
# ============================================================

def _calculate_fatigue(vol: Volunteer, db: Session) -> dict:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_48h = now - timedelta(hours=48)

    tasks_24h = db.query(Assignment).filter(
        Assignment.volunteer_id == vol.id,
        Assignment.status == "completed",
        Assignment.completed_at >= cutoff_24h,
    ).count()

    tasks_48h = db.query(Assignment).filter(
        Assignment.volunteer_id == vol.id,
        Assignment.status == "completed",
        Assignment.completed_at >= cutoff_48h,
    ).count()

    hours_since_last = 0
    if vol.last_task_completed_at:
        hours_since_last = (now - vol.last_task_completed_at).total_seconds() / 3600

    task_24h_score = min(tasks_24h / 3.0, 1.0) * 0.5
    task_48h_score = min(tasks_48h / 5.0, 1.0) * 0.3
    rest_score = min(hours_since_last / 48.0, 1.0) * 0.2 if vol.last_task_completed_at else 0

    fatigue = round(task_24h_score + task_48h_score + rest_score, 3)
    fatigue = min(1.0, max(0.0, fatigue))
    rest_recommended = fatigue >= 0.8

    vol.tasks_last_48h = tasks_48h
    vol.fatigue_score = fatigue
    vol.rest_recommended = rest_recommended

    return {
        "fatigue_score": fatigue,
        "tasks_last_48h": tasks_48h,
        "rest_recommended": rest_recommended,
        "last_task_completed_at": vol.last_task_completed_at,
    }


@router.get("/{volunteer_id}/fatigue/")
async def get_fatigue_score(
    volunteer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get volunteer fatigue/wellness score."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    result = _calculate_fatigue(vol, db)
    db.commit()
    from ..schemas import FatigueResponse
    return FatigueResponse(**result)


# ============================================================
# CERTIFICATE ELIGIBILITY (Task 2.6)
# ============================================================

CERTIFICATE_TIERS = [
    {"name": "First Responder", "required_tasks": 1},
    {"name": "Active Volunteer", "required_tasks": 5},
    {"name": "Community Hero", "required_tasks": 10},
    {"name": "Disaster Relief Champion", "required_tasks": 25},
]


@router.get("/{volunteer_id}/certificate/")
async def get_certificate_eligibility(
    volunteer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get volunteer certificate tier eligibility."""
    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    from ..schemas import CertificateResponse, CertificateTier
    tiers = []
    current_tier = None
    tasks_to_next = 0
    for t in CERTIFICATE_TIERS:
        unlocked = vol.tasks_completed >= t["required_tasks"]
        remaining = max(0, t["required_tasks"] - vol.tasks_completed)
        tiers.append(CertificateTier(name=t["name"], required_tasks=t["required_tasks"], unlocked=unlocked, tasks_remaining=remaining))
        if unlocked:
            current_tier = t["name"]
    for t in CERTIFICATE_TIERS:
        if vol.tasks_completed < t["required_tasks"]:
            tasks_to_next = t["required_tasks"] - vol.tasks_completed
            break
    return CertificateResponse(eligible_tiers=tiers, current_tier=current_tier, tasks_completed=vol.tasks_completed, tasks_to_next=tasks_to_next)


# ============================================================
# SKILL VERIFICATION (Task 3.3)
# ============================================================

@router.post("/{volunteer_id}/verify-skill/", status_code=status.HTTP_201_CREATED)
async def verify_skill(
    volunteer_id: str,
    body: SkillVerifyRequest,
    request: Request,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin marks a volunteer skill as verified."""
    from ..models import SkillVerification
    from ..schemas import SkillVerificationResponse

    vol = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    existing = db.query(SkillVerification).filter(
        SkillVerification.volunteer_id == volunteer_id,
        SkillVerification.skill == body.skill.lower(),
    ).first()

    if existing:
        existing.verified = True
        existing.verified_by = current_user.id
        existing.verified_at = datetime.now(timezone.utc)
        existing.certificate_url = body.certificate_url
        db.commit()
        db.refresh(existing)
        sv = existing
    else:
        sv = SkillVerification(
            volunteer_id=volunteer_id,
            skill=body.skill.lower(),
            verified=True,
            verified_by=current_user.id,
            verified_at=datetime.now(timezone.utc),
            certificate_url=body.certificate_url,
        )
        db.add(sv)
        db.commit()
        db.refresh(sv)

    return SkillVerificationResponse(
        id=sv.id, volunteer_id=sv.volunteer_id, skill=sv.skill,
        verified=sv.verified, verified_by=sv.verified_by,
        certificate_url=sv.certificate_url, verified_at=sv.verified_at,
        created_at=sv.created_at,
    )


@router.get("/{volunteer_id}/skill-verifications/")
async def list_skill_verifications(
    volunteer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List a volunteer's skill verifications."""
    from ..models import SkillVerification
    from ..schemas import SkillVerificationResponse

    verifications = db.query(SkillVerification).filter(
        SkillVerification.volunteer_id == volunteer_id
    ).all()

    return [
        SkillVerificationResponse(
            id=sv.id, volunteer_id=sv.volunteer_id, skill=sv.skill,
            verified=sv.verified, verified_by=sv.verified_by,
            certificate_url=sv.certificate_url, verified_at=sv.verified_at,
            created_at=sv.created_at,
        )
        for sv in verifications
    ]
