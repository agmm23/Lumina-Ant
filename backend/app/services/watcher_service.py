"""
Servicio de vigilancia de fuentes de datos.
Corre como tarea asyncio en background — pollea cada 5s los archivos configurados.
Soporta: CSV, Excel (.xlsx/.xls) y Google Sheets.
Cada WatchedFile pertenece a un usuario; los datos se aislan por user_id.
"""

import asyncio
import os
import json
import hashlib
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import WatchedFile, Venta, Gasto, Inventario, Cliente
from app.services.analytics_service import AnalyticsService
from app.services.csv_import import (
    parse_ventas_df, import_ventas_rows,
    parse_gastos_df, import_gastos_rows,
    parse_inventario_df, import_inventario_rows,
    parse_clientes_df, import_clientes_rows,
)
from app.services.data_reader import ExcelReader, GoogleSheetsReader

logger = logging.getLogger(__name__)

# Contador global — el frontend lo pollea para detectar datos nuevos.
_import_version: int = 0

POLL_INTERVAL = 5     # segundos para CSV/Excel
GSHEETS_INTERVAL = 60 # segundos para Google Sheets (limita llamadas API)
_gsheets_last_poll: dict = {}  # datasource_type → timestamp última poll


def get_import_version() -> int:
    return _import_version


def bump_import_version() -> int:
    """Incrementa el contador. Llamar después de cada importación exitosa vía upload."""
    global _import_version
    _import_version += 1
    return _import_version


# ── Lectura multi-fuente ───────────────────────────────────────────────────────

def _read_dataframe(w: WatchedFile) -> tuple[pd.DataFrame, float]:
    """
    Lee el DataFrame según source_type del watcher.
    Retorna (df, mtime_or_hash) donde el segundo valor detecta cambios.
    """
    source_type = getattr(w, "source_type", "csv") or "csv"
    config = json.loads(getattr(w, "source_config", "{}") or "{}")
    sheet = config.get("sheet") or None

    if source_type == "excel":
        path = w.file_path
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Archivo no encontrado: {path}")
        mtime = os.path.getmtime(path)
        with open(path, "rb") as f:
            content = f.read()
        df = ExcelReader(content).read(sheet=sheet)
        return df, mtime

    elif source_type == "google_sheets":
        from app.config import get_settings
        settings = get_settings()
        api_key = settings.google_sheets_api_key
        spreadsheet_id = config.get("spreadsheet_id", "")
        if not api_key or not spreadsheet_id:
            raise ValueError(
                "Falta GOOGLE_SHEETS_API_KEY o spreadsheet_id para el watcher de Google Sheets."
            )
        reader = GoogleSheetsReader(spreadsheet_id, api_key)
        df = reader.read(sheet=sheet)
        # Usar hash del contenido como indicador de cambio (no hay mtime)
        content_hash = float(
            int(hashlib.md5(df.to_csv(index=False).encode()).hexdigest(), 16) % (10 ** 9)
        )
        return df, content_hash

    else:  # csv (default)
        path = w.file_path
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Archivo no encontrado: {path}")
        mtime = os.path.getmtime(path)
        df = pd.read_csv(path)
        return df, mtime


def _should_poll_gsheets(datasource_type: str) -> bool:
    """Throttle: Google Sheets solo se lee cada GSHEETS_INTERVAL segundos."""
    now = datetime.now(timezone.utc).timestamp()
    last = _gsheets_last_poll.get(datasource_type, 0)
    if now - last >= GSHEETS_INTERVAL:
        _gsheets_last_poll[datasource_type] = now
        return True
    return False


# ── Procesamiento ──────────────────────────────────────────────────────────────

def _process_watcher(w: WatchedFile, db: Session) -> None:
    """Procesa un solo watcher: lee la fuente y sincroniza la DB si hubo cambios.
    Todos los datos se filtran por w.user_id para aislamiento total."""
    global _import_version

    source_type = getattr(w, "source_type", "csv") or "csv"
    user_id = w.user_id

    # Throttle Google Sheets para no saturar la API
    if source_type == "google_sheets" and not _should_poll_gsheets(w.datasource_type):
        return

    # Leer datos de la fuente
    try:
        df, current_mtime = _read_dataframe(w)
    except FileNotFoundError as e:
        w.last_error = str(e)
        db.commit()
        return
    except Exception as e:
        w.last_error = f"Error leyendo {source_type}: {str(e)[:200]}"
        db.commit()
        logger.warning(f"[Watcher] {w.datasource_type} user={user_id} ({source_type}): {e}")
        return

    # Sin cambios → saltar
    if current_mtime == w.last_mtime:
        return

    total_rows = len(df)
    imported = 0

    try:
        changed = False

        if w.datasource_type == 'ventas':
            df = parse_ventas_df(df)
            deleted = db.query(Venta).filter(Venta.user_id == user_id).delete()
            db.flush()
            imported, _ = import_ventas_rows(df.reset_index(drop=True), db, user_id=user_id)
            changed = (imported != w.last_row_count) or (deleted != imported)
            w.last_row_count = total_rows

        elif w.datasource_type == 'gastos':
            df = parse_gastos_df(df)
            deleted = db.query(Gasto).filter(Gasto.user_id == user_id).delete()
            db.flush()
            imported, _ = import_gastos_rows(df.reset_index(drop=True), db, user_id=user_id)
            changed = (imported != w.last_row_count) or (deleted != imported)
            w.last_row_count = total_rows

        elif w.datasource_type == 'inventario':
            df = parse_inventario_df(df)
            csv_ids = set(df['producto_id'].astype(str))
            creados, actualizados, _ = import_inventario_rows(df, db, user_id=user_id)
            orphans = db.query(Inventario).filter(
                Inventario.user_id == user_id,
                Inventario.producto_id.notin_(csv_ids),
            ).delete(synchronize_session='fetch')
            imported = creados + actualizados
            changed = creados > 0 or orphans > 0

        elif w.datasource_type == 'clientes':
            df = parse_clientes_df(df)
            csv_ids = set(df['cliente_id'].astype(str))
            creados, actualizados, _ = import_clientes_rows(df, db, user_id=user_id)
            orphans = db.query(Cliente).filter(
                Cliente.user_id == user_id,
                Cliente.cliente_id.notin_(csv_ids),
            ).delete(synchronize_session='fetch')
            imported = creados + actualizados
            changed = creados > 0 or orphans > 0

        else:
            w.last_error = f"Tipo desconocido: {w.datasource_type}"
            db.commit()
            return

        w.last_mtime = current_mtime
        w.last_imported_at = datetime.now(timezone.utc)
        w.last_import_count = imported
        w.last_error = None
        db.commit()

        if changed:
            _import_version += 1
            logger.info(
                f"[Watcher] {w.datasource_type} user={user_id} ({source_type}): "
                f"sync — {imported} filas (v{_import_version})"
            )

    except Exception as e:
        db.rollback()
        w.last_error = str(e)[:1000]
        w.last_mtime = current_mtime
        db.commit()
        logger.warning(f"[Watcher] {w.datasource_type} user={user_id} error: {e}")


async def watcher_loop() -> None:
    """Bucle principal del watcher. Corre indefinidamente."""
    logger.info("[Watcher] Bucle iniciado — polling cada %ds", POLL_INTERVAL)
    while True:
        try:
            db: Session = SessionLocal()
            try:
                version_before = _import_version
                watchers = db.query(WatchedFile).filter(WatchedFile.enabled == True).all()
                for w in watchers:
                    _process_watcher(w, db)
                if _import_version != version_before:
                    # Ejecutar detección de anomalías para cada usuario con cambios
                    user_ids_changed = {w.user_id for w in watchers}
                    for uid in user_ids_changed:
                        try:
                            AnalyticsService.detect_anomalies(db, uid)
                        except Exception as e:
                            logger.warning(f"[Watcher] Error en detección de anomalías user={uid}: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[Watcher] Error en ciclo: {e}")

        await asyncio.sleep(POLL_INTERVAL)
