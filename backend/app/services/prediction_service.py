"""
Prediction Service — AI-powered need forecasting engine (Task 2.1).

When DisasterAlertSystem detects severity ≥ 4, this engine generates
draft needs based on historical disaster-to-need probability patterns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models import Need, _uuid, _utcnow
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# DISASTER → NEED PROBABILITY PATTERNS
# ============================================================

DISASTER_NEED_PATTERNS = {
    "FLOOD": [
        {"category": "food",    "probability": 0.92, "urgency": 5, "people_multiplier": 1.5},
        {"category": "shelter", "probability": 0.88, "urgency": 5, "people_multiplier": 1.2},
        {"category": "rescue",  "probability": 0.75, "urgency": 5, "people_multiplier": 0.3},
        {"category": "water",   "probability": 0.95, "urgency": 4, "people_multiplier": 2.0},
        {"category": "medical", "probability": 0.60, "urgency": 4, "people_multiplier": 0.5},
    ],
    "CYCLONE": [
        {"category": "shelter", "probability": 0.95, "urgency": 5, "people_multiplier": 2.0},
        {"category": "rescue",  "probability": 0.90, "urgency": 5, "people_multiplier": 0.5},
        {"category": "food",    "probability": 0.85, "urgency": 4, "people_multiplier": 1.5},
        {"category": "medical", "probability": 0.70, "urgency": 4, "people_multiplier": 0.4},
        {"category": "water",   "probability": 0.80, "urgency": 4, "people_multiplier": 1.8},
        {"category": "clothing","probability": 0.65, "urgency": 3, "people_multiplier": 1.0},
    ],
    "EXTREME_HEAT": [
        {"category": "water",   "probability": 0.98, "urgency": 5, "people_multiplier": 3.0},
        {"category": "medical", "probability": 0.80, "urgency": 4, "people_multiplier": 0.5},
        {"category": "shelter", "probability": 0.70, "urgency": 3, "people_multiplier": 0.8},
        {"category": "food",    "probability": 0.65, "urgency": 3, "people_multiplier": 1.0},
    ],
    "THUNDERSTORM": [
        {"category": "shelter", "probability": 0.80, "urgency": 4, "people_multiplier": 1.0},
        {"category": "rescue",  "probability": 0.70, "urgency": 4, "people_multiplier": 0.3},
        {"category": "medical", "probability": 0.60, "urgency": 3, "people_multiplier": 0.3},
        {"category": "food",    "probability": 0.50, "urgency": 3, "people_multiplier": 0.8},
    ],
    "EARTHQUAKE": [
        {"category": "rescue",  "probability": 0.95, "urgency": 5, "people_multiplier": 0.5},
        {"category": "shelter", "probability": 0.93, "urgency": 5, "people_multiplier": 2.0},
        {"category": "medical", "probability": 0.90, "urgency": 5, "people_multiplier": 0.6},
        {"category": "food",    "probability": 0.85, "urgency": 4, "people_multiplier": 1.5},
        {"category": "water",   "probability": 0.88, "urgency": 4, "people_multiplier": 2.0},
    ],
}


CATEGORY_TITLES = {
    "food": "Predicted: Food shortage in affected area",
    "shelter": "Predicted: Temporary shelter needed",
    "rescue": "Predicted: Rescue operations required",
    "water": "Predicted: Clean water supply needed",
    "medical": "Predicted: Medical assistance required",
    "clothing": "Predicted: Emergency clothing distribution needed",
    "sanitation": "Predicted: Sanitation facilities needed",
    "education": "Predicted: Educational support required",
}


async def generate_predicted_needs(
    disaster_type: str,
    center_lat: float,
    center_lon: float,
    affected_radius_km: float,
    estimated_population: int,
    db: Session,
) -> list[dict]:
    """
    Generate predicted need drafts based on historical disaster patterns.
    
    Does NOT auto-create in DB — returns for admin review.
    """
    disaster_type = disaster_type.upper()
    patterns = DISASTER_NEED_PATTERNS.get(disaster_type)
    
    if not patterns:
        logger.warning(f"No prediction patterns for disaster type: {disaster_type}")
        return []

    predicted_needs = []
    
    for pattern in patterns:
        if pattern["probability"] < 0.6:
            continue  # Skip low-probability needs
        
        people_affected = max(1, int(estimated_population * pattern["people_multiplier"]))
        title = CATEGORY_TITLES.get(
            pattern["category"],
            f"Predicted: {pattern['category']} need in disaster zone"
        )
        
        # Add disaster context to title
        title = f"{title} ({disaster_type.title()} Alert)"

        predicted_needs.append({
            "category": pattern["category"],
            "title": title,
            "description": (
                f"AI-predicted need based on {disaster_type.title()} alert. "
                f"Historical probability: {pattern['probability']*100:.0f}%. "
                f"Estimated {people_affected} people affected within {affected_radius_km}km radius."
            ),
            "urgency": pattern["urgency"],
            "people_affected": people_affected,
            "probability": pattern["probability"],
            "latitude": center_lat,
            "longitude": center_lon,
            "status": "predicted",
            "source": "ai_prediction",
        })

    logger.info(
        f"Generated {len(predicted_needs)} predicted needs for "
        f"{disaster_type} at ({center_lat}, {center_lon})"
    )
    
    return predicted_needs


def confirm_predicted_need(need_id: str, db: Session) -> Optional[Need]:
    """Convert a predicted need to 'open' status (admin confirmed)."""
    need = db.query(Need).filter(Need.id == need_id, Need.status == "predicted").first()
    if not need:
        return None
    
    need.status = "open"
    need.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(need)
    
    logger.info(f"Predicted need confirmed: '{need.title}' → open")
    return need


def dismiss_predicted_need(need_id: str, db: Session) -> Optional[Need]:
    """Dismiss a predicted need (admin rejected)."""
    need = db.query(Need).filter(Need.id == need_id, Need.status == "predicted").first()
    if not need:
        return None
    
    need.status = "cancelled"
    need.updated_at = datetime.now(timezone.utc)
    need.notes = (need.notes or "") + " [AI prediction dismissed by admin]"
    db.commit()
    db.refresh(need)
    
    logger.info(f"Predicted need dismissed: '{need.title}'")
    return need
