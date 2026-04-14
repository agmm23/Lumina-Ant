"""
Lumina_Ant - Router del Watcher
Endpoints para gestionar la vigilancia automática de archivos CSV.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.models import WatchedFile, Venta, Gasto, Inventario, Cliente
from app.services.watcher_service import get_import_version
from app.auth.dependencies import get_current_user
from app.auth.models import User

router = APIRouter(prefix="/api/watcher", tags=["watcher"])

VALID_TYPES = {"ventas", "gastos", "inventario", "clientes"}


class WatcherUpsert(BaseModel):
    file_path: str
    source_type: Optional[str] = None      # "csv" | "excel" | "google_sheets"
    source_config: Optional[str] = None    # JSON string: {"sheet": "Hoja1"}
    reset_cursor: Optional[bool] = False   # reinicia mtime para forzar reimport


class WatcherPatch(BaseModel):
    enabled: Optional[bool] = None
    reset_cursor: Optional[bool] = None


# ── Endpoints ───────────────────────────────────────────────────────────────────

def _watcher_dict(w):
    return {
        "datasource_type": w.datasource_type,
        "file_path": w.file_path,
        "source_type": w.source_type,
        "source_name": w.source_name,
        "enabled": w.enabled,
        "last_row_count": w.last_row_count,
        "last_mtime": w.last_mtime,
        "last_imported_at": w.last_imported_at.isoformat() if w.last_imported_at else None,
        "last_import_count": w.last_import_count,
        "last_error": w.last_error,
    }


@router.get("/status")
def get_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Endpoint ligero para polling del frontend."""
    watchers = db.query(WatchedFile).filter(WatchedFile.user_id == current_user.id).all()
    return {
        "import_version": get_import_version(),
        "watchers": [_watcher_dict(w) for w in watchers],
    }


@router.get("/")
def list_watchers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    watchers = db.query(WatchedFile).filter(WatchedFile.user_id == current_user.id).all()
    return [_watcher_dict(w) for w in watchers]


@router.put("/{datasource_type}")
def upsert_watcher(
    datasource_type: str,
    body: WatcherUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if datasource_type not in VALID_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Tipo inválido. Usa: {VALID_TYPES}")

    uid = current_user.id
    w = db.query(WatchedFile).filter(
        WatchedFile.user_id == uid,
        WatchedFile.datasource_type == datasource_type,
    ).first()
    if w:
        w.file_path = body.file_path
        if body.source_type is not None:
            w.source_type = body.source_type
        if body.source_config is not None:
            w.source_config = body.source_config
        if body.reset_cursor:
            w.last_mtime = 0.0
            w.last_row_count = 0
        w.last_error = None
        w.enabled = True
    else:
        w = WatchedFile(
            user_id=uid,
            datasource_type=datasource_type,
            file_path=body.file_path,
            source_type=body.source_type or "csv",
            source_config=body.source_config or "{}",
        )
        db.add(w)
    db.commit()
    db.refresh(w)
    return {"status": "ok", "datasource_type": w.datasource_type, "file_path": w.file_path}


@router.patch("/{datasource_type}")
def patch_watcher(
    datasource_type: str,
    body: WatcherPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    w = db.query(WatchedFile).filter(
        WatchedFile.user_id == current_user.id,
        WatchedFile.datasource_type == datasource_type,
    ).first()
    if not w:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watcher no encontrado")

    if body.enabled is not None:
        w.enabled = body.enabled
    if body.reset_cursor:
        w.last_row_count = 0
        w.last_mtime = 0.0
        w.last_error = None

    db.commit()
    return {"status": "ok", "enabled": w.enabled}


_DATA_MODEL_MAP = {
    "ventas": Venta,
    "gastos": Gasto,
    "inventario": Inventario,
    "clientes": Cliente,
}


@router.delete("/{datasource_type}")
def delete_watcher(
    datasource_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    w = db.query(WatchedFile).filter(
        WatchedFile.user_id == uid,
        WatchedFile.datasource_type == datasource_type,
    ).first()
    if not w:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watcher no encontrado")
    # Borrar también los datos importados de esta fuente para el usuario
    model = _DATA_MODEL_MAP.get(datasource_type)
    if model:
        db.query(model).filter(model.user_id == uid).delete()
    db.delete(w)
    db.commit()
    return {"status": "ok"}
