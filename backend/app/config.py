"""
Application configuration loaded from environment variables.
Uses pydantic-settings for validation and type coercion.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central settings object, populated from .env file."""

    # --- App ---
    APP_NAME: str = "SevaSetu"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production-please"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Google OAuth ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # --- Gemini AI ---
    GEMINI_API_KEY: str = ""

    # --- Firebase Cloud Messaging ---
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-credentials.json"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./smartalloc.db"

    # --- CORS ---
    FRONTEND_LANDING_URL: str = "https://sevasetu-landing-tn51.onrender.com"
    FRONTEND_ADMIN_URL: str = "https://ngo-sevasetu-admin.onrender.com"
    FRONTEND_VOLUNTEER_URL: str = "https://ngo-sevasetu-volunteer.onrender.com"

    # --- File Uploads ---
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # --- OpenWeatherMap ---
    OWM_API_KEY: str = ""

    # --- JWT ---
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # --- Matching Algorithm Weights ---
    MATCH_WEIGHT_DISTANCE: float = 0.40
    MATCH_WEIGHT_SKILL: float = 0.35
    MATCH_WEIGHT_AVAILABILITY: float = 0.25
    MATCH_MAX_DISTANCE_KM: float = 50.0

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:3000",
            "https://sevasetu-landing-tn51.onrender.com",
            "https://ngo-sevasetu-admin.onrender.com",
            "https://ngo-sevasetu-volunteer.onrender.com",
        ]

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
