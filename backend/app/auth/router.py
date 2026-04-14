"""
Router de autenticación: /api/auth/*
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from .schemas import (
    RegisterRequest,
    LoginRequest,
    GoogleLoginRequest,
    TokenResponse,
    UserOut,
    UserConfigOut,
    UpdateConfigRequest,
)
from .service import (
    get_user_by_email,
    create_user_email,
    verify_password,
    create_access_token,
    verify_google_id_token,
    get_or_create_google_user,
)
from .dependencies import get_current_user
from .models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _seed_alerts_for_new_user(db: Session, user_id: int):
    """Crea las configuraciones de alerta estándar para un usuario recién creado."""
    from app.main import seed_alert_configs_for_user
    seed_alert_configs_for_user(db, user_id)


def _token_response(user: User) -> TokenResponse:
    """Helper: construye TokenResponse a partir de un User ORM."""
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Registra un nuevo usuario con email y contraseña."""
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="El correo ya está registrado")
    user = create_user_email(db, body.email, body.password, body.display_name)
    _seed_alerts_for_new_user(db, user.id)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Inicia sesión con email y contraseña."""
    user = get_user_by_email(db, body.email)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return _token_response(user)


@router.post("/google", response_model=TokenResponse)
def login_google(body: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Inicia sesión con Google OAuth (ID token del frontend)."""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth no está configurado en el servidor")
    try:
        payload = verify_google_id_token(body.credential, settings.google_client_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Token de Google inválido o expirado")
    is_new_user, user = get_or_create_google_user(db, payload)
    if is_new_user:
        _seed_alerts_for_new_user(db, user.id)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Devuelve los datos del usuario autenticado."""
    return UserOut.model_validate(current_user)


@router.patch("/config", response_model=UserConfigOut)
def update_config(
    body: UpdateConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza la configuración del usuario (idioma, tema, preferencias de alertas)."""
    config = current_user.config
    if body.language is not None:
        if body.language not in ("es", "en"):
            raise HTTPException(status_code=400, detail="Idioma no soportado. Usa 'es' o 'en'")
        config.language = body.language
    if body.theme is not None:
        if body.theme not in ("light", "dark"):
            raise HTTPException(status_code=400, detail="Tema no soportado. Usa 'light' o 'dark'")
        config.theme = body.theme
    if body.alert_preferences is not None:
        config.alert_preferences = body.alert_preferences
    db.commit()
    db.refresh(config)
    return UserConfigOut.model_validate(config)


@router.post("/logout", status_code=204)
def logout():
    """
    Cierre de sesión. El cliente debe descartar el token localmente.
    En v1 no hay blacklist de tokens (stateless JWT).
    """
    return Response(status_code=204)
