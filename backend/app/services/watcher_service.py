"""
Servicio de vigilancia de archivos CSV.
Corre como tarea asyncio en background — pollea cada 5s los archivos configurados.
"""

import asyncio
import os
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

logger = logging.getLogger(__name__)

# Contador global — el frontend lo pollea para detectar datos nuevos.
_import_version: int = 0

POLL_INTERVAL = 5  # segundos


def get_import_version() -> int:
    return _import_version


def _process_watcher(w: WatchedFile, db: Session) -> None:
    """Procesa un solo watcher: lee el CSV y importa filas nuevas."""
    global _import_version

    path = w.file_path
    if not os.path.isfile(path):
        w.last_error = f"Archivo no encontrado: {path}"
        db.commit()
        return

    mtime = os.path.getmtime(path)
    if mtime == w.last_mtime:
        return  # sin cambios

    try:
        df = pd.read_csv(path)
    except Exception as e:
        w.last_error = f"Error leyendo CSV: {e}"
        w.last_mtime = mtime
        db.commit()
        return

    total_rows = len(df)
    imported = 0

    try:
        changed = False

        if w.datasource_type == 'ventas':
            df = parse_ventas_df(df)
            # Full sync: borrar todo y re-importar
            deleted = db.query(Venta).delete()
            db.flush()
            imported, _ = import_ventas_rows(df.reset_index(drop=True), db)
            changed = (imported != w.last_row_count) or (deleted != imported)
            w.last_row_count = total_rows

        elif w.datasource_type == 'gastos':
            df = parse_gastos_df(df)
            deleted = db.query(Gasto).delete()
            db.flush()
            imported, _ = import_gastos_rows(df.reset_index(drop=True), db)
            changed = (imported != w.last_row_count) or (deleted != imported)
            w.last_row_count = total_rows

        elif w.datasource_type == 'inventario':
            df = parse_inventario_df(df)
            csv_ids = set(df['producto_id'].astype(str))
            creados, actualizados, _ = import_inventario_rows(df, db)
            # Eliminar productos que ya no están en el CSV
            orphans = db.query(Inventario).filter(
                Inventario.producto_id.notin_(csv_ids)
            ).delete(synchronize_session='fetch')
            imported = creados + actualizados
            changed = creados > 0 or orphans > 0

        elif w.datasource_type == 'clientes':
            df = parse_clientes_df(df)
            csv_ids = set(df['cliente_id'].astype(str))
            creados, actualizados, _ = import_clientes_rows(df, db)
            orphans = db.query(Cliente).filter(
                Cliente.cliente_id.notin_(csv_ids)
            ).delete(synchronize_session='fetch')
            imported = creados + actualizados
            changed = creados > 0 or orphans > 0

        else:
            w.last_error = f"Tipo desconocido: {w.datasource_type}"
            db.commit()
            return

        w.last_mtime = mtime
        w.last_imported_at = datetime.now(timezone.utc)
        w.last_import_count = imported
        w.last_error = None
        db.commit()

        if changed:
            _import_version += 1
            logger.info(f"[Watcher] {w.datasource_type}: sync completo — {imported} filas (v{_import_version})")

    except Exception as e:
        db.rollback()
        w.last_error = str(e)[:1000]
        w.last_mtime = mtime
        db.commit()
        logger.warning(f"[Watcher] {w.datasource_type} error: {e}")


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
                # Si hubo cambios en los datos, correr detección de anomalías
                if _import_version != version_before:
                    try:
                        AnalyticsService.detect_anomalies(db)
                    except Exception as e:
                        logger.warning(f"[Watcher] Error en detección de anomalías: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[Watcher] Error en ciclo: {e}")

        await asyncio.sleep(POLL_INTERVAL)
