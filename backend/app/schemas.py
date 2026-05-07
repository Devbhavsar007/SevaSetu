"""
Pydantic schemas for request validation and response serialization.
Every input is validated, every output is typed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================
# ENUMS
# ============================================================

class UserRole(str, Enum):
    admin = "admin"
    volunteer = "volunteer"


class NeedCategory(str, Enum):
    medical = "medical"
    food = "food"
    shelter = "shelter"
    rescue = "rescue"
    education = "education"
    clothing = "clothing"
    sanitation = "sanitation"
    water = "water"
    other = "other"


class NeedStatus(str, Enum):
    open = "open"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    cancelled = "cancelled"
    predicted = "predicted"  # NEW: AI-predicted draft needs (Task 2.1)


class VolunteerAvailability(str, Enum):
    available = "available"
    busy = "busy"
    offline = "offline"


class AssignmentStatus(str, Enum):
    assigned = "assigned"
    accepted = "accepted"
    in_progress = "in_progress"
    completed = "completed"
    rejected = "rejected"


class VerificationStatus(str, Enum):
    unverified = "unverified"
    verified = "verified"
    false_alarm = "false_alarm"


class VehicleType(str, Enum):
    bike = "bike"
    car = "car"
    van = "van"
    truck = "truck"
    none = "none"


class NeedSource(str, Enum):
    manual = "manual"
    ocr = "ocr"
    broadcast = "broadcast"
    api = "api"
    ai_prediction = "ai_prediction"  # NEW: From prediction engine (Task 2.1)
    sos = "sos"  # NEW: From SOS panic button (Task 2.5)


# ============================================================
# AUTH SCHEMAS
# ============================================================

class GoogleAuthRequest(BaseModel):
    """Frontend sends the Google ID token after sign-in."""
    id_token: str = Field(..., min_length=10, description="Google OAuth ID token")
    role: UserRole = Field(default=UserRole.volunteer, description="Requested role")
    fcm_token: Optional[str] = Field(default=None, description="Firebase Cloud Messaging token")


class EmailRegisterRequest(BaseModel):
    """Register with email and password."""
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    role: UserRole = Field(default=UserRole.volunteer)


class EmailLoginRequest(BaseModel):
    """Login with email and password."""
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class TokenData(BaseModel):
    user_id: str
    email: str
    role: str


# ============================================================
# USER SCHEMAS
# ============================================================

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    picture: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    picture: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    is_new_user: bool = False


# ============================================================
# VOLUNTEER SCHEMAS
# ============================================================

class VolunteerCreateRequest(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=20)
    skills: List[str] = Field(default_factory=list, description="List of skill tags")
    has_vehicle: bool = False
    vehicle_type: Optional[VehicleType] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v):
        valid_skills = {
            "medical", "first_aid", "nursing", "cooking", "driving",
            "logistics", "construction", "teaching", "counseling",
            "swimming", "cleaning", "it_support", "translation",
            "childcare", "elderly_care", "fundraising", "photography",
            "social_media", "legal_aid", "mental_health"
        }
        for skill in v:
            if skill.lower() not in valid_skills:
                raise ValueError(f"Invalid skill: '{skill}'. Valid: {sorted(valid_skills)}")
        return [s.lower() for s in v]

    @field_validator("vehicle_type")
    @classmethod
    def validate_vehicle(cls, v, info):
        if info.data.get("has_vehicle") and v is None:
            raise ValueError("vehicle_type is required when has_vehicle is True")
        if not info.data.get("has_vehicle") and v and v != VehicleType.none:
            raise ValueError("Cannot set vehicle_type when has_vehicle is False")
        return v


class VolunteerUpdateRequest(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=20)
    skills: Optional[List[str]] = None
    has_vehicle: Optional[bool] = None
    vehicle_type: Optional[VehicleType] = None
    address: Optional[str] = Field(default=None, max_length=500)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v):
        if v is None:
            return v
        valid_skills = {
            "medical", "first_aid", "nursing", "cooking", "driving",
            "logistics", "construction", "teaching", "counseling",
            "swimming", "cleaning", "it_support", "translation",
            "childcare", "elderly_care", "fundraising", "photography",
            "social_media", "legal_aid", "mental_health"
        }
        for skill in v:
            if skill.lower() not in valid_skills:
                raise ValueError(f"Invalid skill: '{skill}'. Valid: {sorted(valid_skills)}")
        return [s.lower() for s in v]


class VolunteerLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


class VolunteerAvailabilityUpdate(BaseModel):
    availability: VolunteerAvailability


class VolunteerFCMUpdate(BaseModel):
    fcm_token: str = Field(..., min_length=10)


class VolunteerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    phone: Optional[str] = None
    skills: List[str] = []
    has_vehicle: bool
    vehicle_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    availability: str
    current_task_id: Optional[str] = None
    tasks_completed: int
    rating: float
    total_ratings: int
    created_at: datetime
    updated_at: datetime

    # Nested user info
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_picture: Optional[str] = None


class VolunteerBriefResponse(BaseModel):
    """Lightweight volunteer data for lists and map markers."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_name: str
    skills: List[str]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    availability: str
    has_vehicle: bool
    tasks_completed: int
    rating: float


# ============================================================
# NEED SCHEMAS
# ============================================================

class NeedCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: NeedCategory
    urgency: int = Field(default=3, ge=1, le=5)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)
    people_affected: int = Field(default=1, ge=1, le=100000)
    source: NeedSource = NeedSource.manual
    ocr_raw_text: Optional[str] = None
    notes: Optional[str] = None


class NeedUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[NeedCategory] = None
    urgency: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[NeedStatus] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)
    people_affected: Optional[int] = Field(default=None, ge=1, le=100000)
    verification_status: Optional[VerificationStatus] = None
    notes: Optional[str] = None


class NeedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reported_by: Optional[str] = None
    reporter_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str
    urgency: int
    status: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    people_affected: int
    source: str
    ocr_raw_text: Optional[str] = None
    images: List[str] = []
    assigned_volunteer_id: Optional[str] = None
    assigned_volunteer_name: Optional[str] = None
    verification_status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class NeedBriefResponse(BaseModel):
    """Lightweight need data for map markers."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    category: str
    urgency: int
    status: str
    latitude: float
    longitude: float
    people_affected: int
    created_at: datetime


# ============================================================
# ASSIGNMENT SCHEMAS
# ============================================================

class AssignmentCreateRequest(BaseModel):
    need_id: str
    volunteer_id: str
    admin_notes: Optional[str] = None


class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus
    rejection_reason: Optional[str] = Field(default=None, max_length=500)
    feedback: Optional[str] = Field(default=None, max_length=2000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection(cls, v, info):
        if info.data.get("status") == AssignmentStatus.rejected and not v:
            raise ValueError("rejection_reason is required when rejecting an assignment")
        return v


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    need_id: str
    volunteer_id: str
    status: str
    match_score: Optional[float] = None
    distance_km: Optional[float] = None
    assigned_at: datetime
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None
    admin_notes: Optional[str] = None

    # Nested info
    need_title: Optional[str] = None
    need_category: Optional[str] = None
    volunteer_name: Optional[str] = None


# ============================================================
# BROADCAST SCHEMAS
# ============================================================

class BroadcastCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    message: str = Field(..., min_length=10, max_length=2000)
    category: Optional[NeedCategory] = None
    urgency: int = Field(default=3, ge=1, le=5)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=5.0, ge=0.5, le=100.0)
    need_id: Optional[str] = None


class BroadcastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sent_by: Optional[str] = None
    sender_name: Optional[str] = None
    title: str
    message: str
    category: Optional[str] = None
    urgency: int
    latitude: float
    longitude: float
    radius_km: float
    recipients_count: int
    need_id: Optional[str] = None
    created_at: datetime


# ============================================================
# OCR SCHEMAS
# ============================================================

class OCRExtractResponse(BaseModel):
    raw_text: str
    original_language: Optional[str] = None
    structured_data: Optional["OCRStructuredData"] = None
    confidence: float = Field(ge=0.0, le=1.0)


class OCRStructuredData(BaseModel):
    """Structured data extracted from OCR text by Gemini AI."""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[NeedCategory] = None
    urgency: Optional[int] = Field(default=None, ge=1, le=5)
    location_text: Optional[str] = None
    people_affected: Optional[int] = None
    key_issues: List[str] = []


# ============================================================
# ANALYTICS SCHEMAS
# ============================================================

class DashboardSummary(BaseModel):
    total_needs: int
    open_needs: int
    resolved_needs: int
    in_progress_needs: int
    total_volunteers: int
    active_volunteers: int
    busy_volunteers: int
    total_assignments: int
    completed_assignments: int
    avg_response_time_hours: Optional[float] = None
    people_helped: int


class CategoryBreakdown(BaseModel):
    category: str
    count: int
    open_count: int
    resolved_count: int


class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    intensity: float  # Based on urgency * people_affected
    category: str
    need_id: str
    title: str


class TimelinePoint(BaseModel):
    date: str  # YYYY-MM-DD
    needs_created: int
    needs_resolved: int


# ============================================================
# MATCHING SCHEMAS
# ============================================================

class MatchSuggestion(BaseModel):
    volunteer: VolunteerBriefResponse
    match_score: float = Field(ge=0.0, le=100.0)
    distance_km: float
    skill_match_pct: float
    reasons: List[str]  # Human-readable reasons for the match


class MatchSuggestionsResponse(BaseModel):
    need_id: str
    need_title: str
    need_category: str
    suggestions: List[MatchSuggestion]
    total_available: int


# ============================================================
# COMMON / PAGINATION
# ============================================================

class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    per_page: int
    total_pages: int


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int


# ============================================================
# Resolve forward references for Python 3.8
# ============================================================
OCRExtractResponse.model_rebuild()


# ============================================================
# PREDICTION SCHEMAS (Task 2.1)
# ============================================================

class PredictionGenerateRequest(BaseModel):
    disaster_type: str = Field(..., description="FLOOD, CYCLONE, EXTREME_HEAT, THUNDERSTORM")
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=10.0, ge=0.5, le=200)
    estimated_population: int = Field(default=1000, ge=1)


class PredictedNeed(BaseModel):
    category: str
    title: str
    urgency: int
    people_affected: int
    probability: float
    latitude: float
    longitude: float


class PredictionResponse(BaseModel):
    predicted_needs: List[PredictedNeed]
    confidence_score: float
    disaster_type: str


# ============================================================
# FATIGUE SCHEMAS (Task 2.2)
# ============================================================

class FatigueResponse(BaseModel):
    fatigue_score: float
    tasks_last_48h: int
    rest_recommended: bool
    last_task_completed_at: Optional[datetime] = None


# ============================================================
# INVENTORY SCHEMAS (Task 2.3)
# ============================================================

class InventoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)


class InventoryItemCreateRequest(BaseModel):
    category: str = Field(..., min_length=2, max_length=50)
    item_name: str = Field(..., min_length=2, max_length=255)
    quantity: int = Field(default=0, ge=0)
    unit: str = Field(default="units", max_length=50)
    minimum_threshold: int = Field(default=10, ge=0)


class InventoryItemAdjust(BaseModel):
    quantity_change: int  # positive = add, negative = remove


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    inventory_id: str
    category: str
    item_name: str
    quantity: int
    unit: str
    minimum_threshold: int
    is_low_stock: bool = False
    last_updated: Optional[datetime] = None


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    managed_by: Optional[str] = None
    items: List[InventoryItemResponse] = []
    total_items: int = 0
    low_stock_count: int = 0
    created_at: Optional[datetime] = None


class NearbyInventoryResponse(BaseModel):
    inventory_id: str
    name: str
    distance_km: float
    stock: int
    unit: str
    category: str


# ============================================================
# SOS SCHEMAS (Task 2.5)
# ============================================================

class SOSRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    message: str = Field(default="SOS triggered", max_length=500)


class SOSResponse(BaseModel):
    sos_id: str
    need_id: str
    message: str
    estimated_response_time: str


# ============================================================
# CERTIFICATE SCHEMAS (Task 2.6)
# ============================================================

class CertificateTier(BaseModel):
    name: str
    required_tasks: int
    unlocked: bool
    tasks_remaining: int


class CertificateResponse(BaseModel):
    eligible_tiers: List[CertificateTier]
    current_tier: Optional[str] = None
    tasks_completed: int
    tasks_to_next: int


# ============================================================
# VOICE INPUT SCHEMAS (Task 2.7)
# ============================================================

class StructureTextRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=5000)
    language: str = Field(default="en-IN")


# ============================================================
# SKILL VERIFICATION SCHEMAS (Task 3.3)
# ============================================================

class SkillVerifyRequest(BaseModel):
    skill: str = Field(..., min_length=1, max_length=100)
    certificate_url: Optional[str] = Field(default=None, max_length=512)


class SkillVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    volunteer_id: str
    skill: str
    verified: bool
    verified_by: Optional[str] = None
    certificate_url: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime


# ============================================================
# AUDIT SCHEMAS (Task 3.2)
# ============================================================

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditSummaryResponse(BaseModel):
    actions_today: int
    top_actors: List[dict]
    most_common_actions: List[dict]
    suspicious_activity: List[dict]
