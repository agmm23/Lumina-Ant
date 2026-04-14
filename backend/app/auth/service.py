"""
Servicio de autenticación: hashing, JWT y gestión de usuarios.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from .models import User, UserConfig

settings = get_settings()


# ── Contraseñas ──────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# ── Google OAuth ─────────────────────────────────────────────────────────────

def verify_google_id_token(credential: str, client_id: str) -> dict:
    """
    Verifica un ID token de Google usando las claves públicas de Google.
    Devuelve el payload con sub, email, name, picture.
    Lanza ValueError si el token es inválido.
    """
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    idinfo = id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        client_id,
    )
    return idinfo


# ── Usuarios ─────────────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _create_config_for(db: Session, user: User) -> None:
    """Crea el UserConfig asociado a un User recién creado."""
    config = UserConfig(user_id=user.id)
    db.add(config)


def create_user_email(
    db: Session,
    email: str,
    password: str,
    display_name: Optional[str] = None,
) -> User:
    """Crea un usuario con email/password y su configuración inicial."""
    user = User(
        email=email,
        hashed_password=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.flush()  # obtener user.id sin commit
    _create_config_for(db, user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_google_user(db: Session, google_payload: dict) -> tuple:
    """
    Busca o crea un usuario a partir del payload de Google.
    Si existe por google_sub → actualiza avatar y devuelve (False, user).
    Si existe por email sin google_sub → vincula la cuenta, devuelve (False, user).
    Si no existe → crea nuevo usuario, devuelve (True, user).
    """
    google_sub = google_payload["sub"]
    email = google_payload.get("email", "")
    name = google_payload.get("name")
    picture = google_payload.get("picture")

    # Buscar por google_sub
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if user:
        user.avatar_url = picture
        db.commit()
        db.refresh(user)
        return False, user

    # Buscar por email y vincular cuenta
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_sub = google_sub
            user.avatar_url = picture
            if not user.display_name:
                user.display_name = name
            db.commit()
            db.refresh(user)
            return False, user

    # Crear nuevo usuario
    user = User(
        email=email,
        google_sub=google_sub,
        display_name=name,
        avatar_url=picture,
    )
    db.add(user)
    db.flush()
    _create_config_for(db, user)
    db.commit()
    db.refresh(user)
    return True, user
