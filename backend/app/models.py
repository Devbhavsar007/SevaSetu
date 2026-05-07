"""
SQLAlchemy ORM models for the Smart Resource Allocation system.
All tables: users, volunteers, needs, assignments, audit_log, broadcasts.
"""

from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# USER — anyone who logs in (admin or volunteer)
# ============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    picture = Column(String(512))
    role = Column(String(20), nullable=False, default="volunteer")  # 'admin' | 'volunteer'
    google_id = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)  # For email/password auth
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    volunteer_profile = relationship("Volunteer", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reported_needs = relationship("Need", back_populates="reporter", foreign_keys="Need.reported_by")
    audit_logs = relationship("AuditLog", back_populates="user")
    broadcasts_sent = relationship("Broadcast", back_populates="sender")

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"


# ============================================================
# VOLUNTEER — extended profile for a volunteer user
# ============================================================
class Volunteer(Base):
    __tablename__ = "volunteers"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    phone = Column(String(20))
    skills = Column(Text, default="[]")  # JSON array stored as text
    has_vehicle = Column(Boolean, default=False)
    vehicle_type = Column(String(50))  # 'bike', 'car', 'van', 'truck', None
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(String(500))
    availability = Column(String(20), default="available")  # 'available' | 'busy' | 'offline'
    current_task_id = Column(String(36))
    tasks_completed = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    total_ratings = Column(Integer, default=0)
    fcm_token = Column(String(512))
    # NEW: Fatigue tracking (Task 2.2)
    last_task_completed_at = Column(DateTime, nullable=True)
    tasks_last_48h = Column(Integer, default=0)
    fatigue_score = Column(Float, default=0.0)  # 0.0 (fresh) to 1.0 (burned out)
    rest_recommended = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    user = relationship("User", back_populates="volunteer_profile")
    assignments = relationship("Assignment", back_populates="volunteer")

    # Indexes for geospatial-like queries
    __table_args__ = (
        Index("idx_volunteer_location", "latitude", "longitude"),
        Index("idx_volunteer_availability", "availability"),
    )

    @property
    def skills_list(self) -> list[str]:
        try:
            return json.loads(self.skills) if self.skills else []
        except (json.JSONDecodeError, TypeError):
            return []

    @skills_list.setter
    def skills_list(self, value: list[str]):
        self.skills = json.dumps(value)

    def update_rating(self, new_rating: int):
        """Incrementally update average rating."""
        self.total_ratings += 1
        self.rating = (
            (self.rating * (self.total_ratings - 1) + new_rating)
            / self.total_ratings
        )

    def __repr__(self):
        return f"<Volunteer {self.user_id} ({self.availability})>"


# ============================================================
# NEED — a community request/requirement
# ============================================================
class Need(Base):
    __tablename__ = "needs"

    id = Column(String(36), primary_key=True, default=_uuid)
    reported_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False)  # medical, food, shelter, rescue, education, clothing, sanitation, water, other
    urgency = Column(Integer, nullable=False, default=3)  # 1 (low) to 5 (critical)
    status = Column(String(20), nullable=False, default="open")  # open, assigned, in_progress, resolved, cancelled
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500))
    people_affected = Column(Integer, default=1)
    source = Column(String(20), default="manual")  # manual, ocr, broadcast, api
    ocr_raw_text = Column(Text)
    images = Column(Text, default="[]")  # JSON array of image filenames
    assigned_volunteer_id = Column(String(36), ForeignKey("volunteers.id", ondelete="SET NULL"), nullable=True)
    verification_status = Column(String(20), default="unverified")  # unverified, verified, false_alarm
    notes = Column(Text)  # Admin notes
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    resolved_at = Column(DateTime)

    # Relationships
    reporter = relationship("User", back_populates="reported_needs", foreign_keys=[reported_by])
    assigned_volunteer = relationship("Volunteer", foreign_keys=[assigned_volunteer_id])
    assignments = relationship("Assignment", back_populates="need", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_need_location", "latitude", "longitude"),
        Index("idx_need_status", "status"),
        Index("idx_need_category", "category"),
        Index("idx_need_urgency", "urgency"),
    )

    @property
    def images_list(self) -> list[str]:
        try:
            return json.loads(self.images) if self.images else []
        except (json.JSONDecodeError, TypeError):
            return []

    @images_list.setter
    def images_list(self, value: list[str]):
        self.images = json.dumps(value)

    def __repr__(self):
        return f"<Need '{self.title}' [{self.category}] urgency={self.urgency}>"


# ============================================================
# ASSIGNMENT — links a volunteer to a need
# ============================================================
class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(String(36), primary_key=True, default=_uuid)
    need_id = Column(String(36), ForeignKey("needs.id", ondelete="CASCADE"), nullable=False)
    volunteer_id = Column(String(36), ForeignKey("volunteers.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="assigned")  # assigned, accepted, in_progress, completed, rejected
    match_score = Column(Float)
    distance_km = Column(Float)
    assigned_at = Column(DateTime, default=_utcnow)
    accepted_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    rejection_reason = Column(String(500))
    feedback = Column(Text)
    rating = Column(Integer)  # 1–5 rating from admin/reporter
    admin_notes = Column(Text)

    # Relationships
    need = relationship("Need", back_populates="assignments")
    volunteer = relationship("Volunteer", back_populates="assignments")

    __table_args__ = (
        Index("idx_assignment_status", "status"),
        Index("idx_assignment_need", "need_id"),
        Index("idx_assignment_volunteer", "volunteer_id"),
    )

    def __repr__(self):
        return f"<Assignment need={self.need_id} vol={self.volunteer_id} ({self.status})>"


# ============================================================
# AUDIT LOG — tracks every important action for accountability
# ============================================================
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., 'need.created', 'volunteer.assigned', 'broadcast.sent'
    entity_type = Column(String(50))  # 'need', 'volunteer', 'assignment', 'broadcast'
    entity_id = Column(String(36))
    details = Column(Text)  # JSON blob with extra context
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_action", "action"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_created", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} by={self.user_id}>"


# ============================================================
# BROADCAST — mass alert sent to volunteers in a radius
# ============================================================
class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(String(36), primary_key=True, default=_uuid)
    sent_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(50))
    urgency = Column(Integer, default=3)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False, default=5.0)
    recipients_count = Column(Integer, default=0)
    need_id = Column(String(36), ForeignKey("needs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    sender = relationship("User", back_populates="broadcasts_sent")
    need = relationship("Need")

    def __repr__(self):
        return f"<Broadcast '{self.title}' r={self.radius_km}km>"


# ============================================================
# INVENTORY — warehouse/stock location (Task 2.3)
# ============================================================
class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)  # "Andheri NGO Warehouse"
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(String(500))
    managed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    items = relationship("InventoryItem", back_populates="inventory", cascade="all, delete-orphan")
    manager = relationship("User")

    def __repr__(self):
        return f"<Inventory '{self.name}'>"


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    inventory_id = Column(String(36), ForeignKey("inventories.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(50), nullable=False)  # matches NeedCategory
    item_name = Column(String(255), nullable=False)  # "Food Packets - 1kg"
    quantity = Column(Integer, default=0)
    unit = Column(String(50), default="units")  # "packets", "liters", "sets"
    minimum_threshold = Column(Integer, default=10)  # alert when below this
    last_updated = Column(DateTime, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    inventory = relationship("Inventory", back_populates="items")

    __table_args__ = (
        Index("idx_inventory_item_category", "category"),
    )

    def __repr__(self):
        return f"<InventoryItem '{self.item_name}' qty={self.quantity}>"


# ============================================================
# SKILL VERIFICATION — admin-verified volunteer skills (Task 3.3)
# ============================================================
class SkillVerification(Base):
    __tablename__ = "skill_verifications"

    id = Column(String(36), primary_key=True, default=_uuid)
    volunteer_id = Column(String(36), ForeignKey("volunteers.id", ondelete="CASCADE"), nullable=False)
    skill = Column(String(100), nullable=False)
    verified = Column(Boolean, default=False)
    verified_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    certificate_url = Column(String(512), nullable=True)  # uploaded proof
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    volunteer = relationship("Volunteer")
    verifier = relationship("User")

    __table_args__ = (
        Index("idx_skill_verification_volunteer", "volunteer_id"),
        Index("idx_skill_verification_skill", "skill"),
    )

    def __repr__(self):
        return f"<SkillVerification {self.skill} verified={self.verified}>"
