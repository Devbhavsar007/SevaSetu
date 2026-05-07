from __future__ import annotations

"""
Inventory routes — Resource warehouse management (Task 2.3).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Inventory, InventoryItem, AuditLog
from ..schemas import (
    InventoryCreateRequest, InventoryItemCreateRequest, InventoryItemAdjust,
    InventoryResponse, InventoryItemResponse, NearbyInventoryResponse,
    MessageResponse,
)
from ..middleware.auth import get_current_user, get_current_admin
from ..services.geo_service import haversine_distance, bounding_box

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _inv_to_response(inv: Inventory) -> InventoryResponse:
    """Convert Inventory model to response with items."""
    items = []
    low_stock = 0
    for item in inv.items:
        is_low = item.quantity < item.minimum_threshold
        if is_low:
            low_stock += 1
        items.append(InventoryItemResponse(
            id=item.id,
            inventory_id=item.inventory_id,
            category=item.category,
            item_name=item.item_name,
            quantity=item.quantity,
            unit=item.unit,
            minimum_threshold=item.minimum_threshold,
            is_low_stock=is_low,
            last_updated=item.last_updated,
        ))

    return InventoryResponse(
        id=inv.id,
        name=inv.name,
        latitude=inv.latitude,
        longitude=inv.longitude,
        address=inv.address,
        managed_by=inv.managed_by,
        items=items,
        total_items=len(items),
        low_stock_count=low_stock,
        created_at=inv.created_at,
    )


@router.post("/", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory(
    body: InventoryCreateRequest,
    request: Request,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Create a new inventory/warehouse location. Admin only."""
    inv = Inventory(
        name=body.name,
        latitude=body.latitude,
        longitude=body.longitude,
        address=body.address,
        managed_by=current_user.id,
    )
    db.add(inv)

    audit = AuditLog(
        user_id=current_user.id,
        action="inventory.created",
        entity_type="inventory",
        entity_id=inv.id,
        details=json.dumps({"name": body.name}),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(inv)

    return _inv_to_response(inv)


@router.get("/", response_model=List[InventoryResponse])
async def list_inventories(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all inventory locations with stock levels."""
    inventories = db.query(Inventory).all()
    return [_inv_to_response(inv) for inv in inventories]


@router.post("/{inventory_id}/items/", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def add_inventory_item(
    inventory_id: str,
    body: InventoryItemCreateRequest,
    request: Request,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Add or update an item in an inventory."""
    inv = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory not found")

    # Check if item already exists
    existing = db.query(InventoryItem).filter(
        InventoryItem.inventory_id == inventory_id,
        InventoryItem.item_name == body.item_name,
    ).first()

    if existing:
        existing.quantity = body.quantity
        existing.unit = body.unit
        existing.minimum_threshold = body.minimum_threshold
        existing.last_updated = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        item = existing
    else:
        item = InventoryItem(
            inventory_id=inventory_id,
            category=body.category,
            item_name=body.item_name,
            quantity=body.quantity,
            unit=body.unit,
            minimum_threshold=body.minimum_threshold,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

    return InventoryItemResponse(
        id=item.id,
        inventory_id=item.inventory_id,
        category=item.category,
        item_name=item.item_name,
        quantity=item.quantity,
        unit=item.unit,
        minimum_threshold=item.minimum_threshold,
        is_low_stock=item.quantity < item.minimum_threshold,
        last_updated=item.last_updated,
    )


@router.patch("/items/{item_id}/", response_model=InventoryItemResponse)
async def adjust_item_quantity(
    item_id: str,
    body: InventoryItemAdjust,
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Adjust item quantity (+/-)."""
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    item.quantity = max(0, item.quantity + body.quantity_change)
    item.last_updated = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    return InventoryItemResponse(
        id=item.id,
        inventory_id=item.inventory_id,
        category=item.category,
        item_name=item.item_name,
        quantity=item.quantity,
        unit=item.unit,
        minimum_threshold=item.minimum_threshold,
        is_low_stock=item.quantity < item.minimum_threshold,
        last_updated=item.last_updated,
    )


@router.get("/nearby/", response_model=List[NearbyInventoryResponse])
async def find_nearby_inventory(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    category: Optional[str] = Query(default=None),
    radius_km: float = Query(default=50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find nearest inventory with available stock for a category."""
    min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius_km)
    
    query = db.query(Inventory).filter(
        Inventory.latitude.isnot(None),
        Inventory.longitude.isnot(None),
        Inventory.latitude.between(min_lat, max_lat),
        Inventory.longitude.between(min_lon, max_lon),
    )
    inventories = query.all()

    results = []
    for inv in inventories:
        dist = haversine_distance(lat, lon, inv.latitude, inv.longitude)
        if dist > radius_km:
            continue

        for item in inv.items:
            if category and item.category != category:
                continue
            if item.quantity > 0:
                results.append(NearbyInventoryResponse(
                    inventory_id=inv.id,
                    name=inv.name,
                    distance_km=round(dist, 2),
                    stock=item.quantity,
                    unit=item.unit,
                    category=item.category,
                ))

    results.sort(key=lambda x: x.distance_km)
    return results


@router.get("/alerts/", response_model=List[InventoryItemResponse])
async def get_low_stock_alerts(
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get items below minimum threshold."""
    items = db.query(InventoryItem).all()
    alerts = []
    for item in items:
        if item.quantity < item.minimum_threshold:
            alerts.append(InventoryItemResponse(
                id=item.id,
                inventory_id=item.inventory_id,
                category=item.category,
                item_name=item.item_name,
                quantity=item.quantity,
                unit=item.unit,
                minimum_threshold=item.minimum_threshold,
                is_low_stock=True,
                last_updated=item.last_updated,
            ))
    return alerts
