from __future__ import annotations

"""
Prediction routes — AI-powered need forecasting (Task 2.1).
"""

import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Need, AuditLog
from ..schemas import (
    PredictionGenerateRequest, PredictionResponse, PredictedNeed,
    NeedResponse, MessageResponse,
)
from ..middleware.auth import get_current_user, get_current_admin
from ..services.prediction_service import (
    generate_predicted_needs, confirm_predicted_need, dismiss_predicted_need,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.post("/generate/", response_model=PredictionResponse)
async def generate_predictions(
    body: PredictionGenerateRequest,
    request: Request,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Generate predicted needs based on disaster type and location.
    Creates draft needs with status='predicted' for admin review.
    """
    predicted = await generate_predicted_needs(
        disaster_type=body.disaster_type,
        center_lat=body.lat,
        center_lon=body.lon,
        affected_radius_km=body.radius_km,
        estimated_population=body.estimated_population,
        db=db,
    )

    # Create predicted needs in DB
    created_needs = []
    for p in predicted:
        need = Need(
            title=p["title"],
            description=p["description"],
            category=p["category"],
            urgency=p["urgency"],
            latitude=p["latitude"],
            longitude=p["longitude"],
            people_affected=p["people_affected"],
            status="predicted",
            source="ai_prediction",
            reported_by=current_user.id,
        )
        db.add(need)
        created_needs.append(p)

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="prediction.generated",
        entity_type="prediction",
        details=json.dumps({
            "disaster_type": body.disaster_type,
            "count": len(created_needs),
            "population": body.estimated_population,
        }),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    # Emit WebSocket event
    try:
        from .realtime import emit_event
        await emit_event("prediction.generated", {
            "disaster_type": body.disaster_type,
            "count": len(created_needs),
            "lat": body.lat,
            "lon": body.lon,
        }, room="admin")
    except Exception as e:
        logger.warning(f"WS emit failed for prediction.generated: {e}")

    return PredictionResponse(
        predicted_needs=[PredictedNeed(**p) for p in created_needs],
        confidence_score=sum(p["probability"] for p in created_needs) / max(len(created_needs), 1),
        disaster_type=body.disaster_type,
    )


@router.get("/", response_model=List[NeedResponse])
async def list_predicted_needs(
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List all unreviewed predicted needs."""
    needs = db.query(Need).filter(Need.status == "predicted").order_by(Need.created_at.desc()).all()

    from .needs import _need_to_response
    return [_need_to_response(n, db) for n in needs]


@router.patch("/{need_id}/confirm/", response_model=MessageResponse)
async def confirm_prediction(
    need_id: str,
    request: Request,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin confirms a predicted need → converts to 'open' status."""
    need = confirm_predicted_need(need_id, db)
    if not need:
        raise HTTPException(status_code=404, detail="Predicted need not found")

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="prediction.confirmed",
        entity_type="need",
        entity_id=need.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    # Emit WebSocket
    try:
        from .realtime import emit_event
        await emit_event("need.created", {
            "id": need.id, "title": need.title,
            "category": need.category, "urgency": need.urgency,
            "status": "open", "source": "ai_prediction",
        }, room="admin")
    except Exception:
        pass

    return MessageResponse(message=f"Predicted need '{need.title}' confirmed and is now open")


@router.patch("/{need_id}/dismiss/", response_model=MessageResponse)
async def dismiss_prediction(
    need_id: str,
    request: Request,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin dismisses a predicted need."""
    need = dismiss_predicted_need(need_id, db)
    if not need:
        raise HTTPException(status_code=404, detail="Predicted need not found")

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="prediction.dismissed",
        entity_type="need",
        entity_id=need.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    return MessageResponse(message=f"Predicted need '{need.title}' dismissed")
