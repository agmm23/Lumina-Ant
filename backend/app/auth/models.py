"""
Modelos de autenticación: User y UserConfig.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)   # null en cuentas Google-only
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    config = relationship(
        "UserConfig",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    language = Column(String(10), default="es", nullable=False)
    theme = Column(String(10), default="light", nullable=False)
    alert_preferences = Column(String(2000), default="{}", nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="config")
