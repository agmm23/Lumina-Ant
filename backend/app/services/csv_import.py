"""
Funciones compartidas de parseo e importación de CSV.
Usadas tanto por los endpoints de upload como por el watcher automático.
"""

import os
import pandas as pd
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.models import Venta, Gasto, Inventario, Cliente, WatchedFile

# Directorio donde se guardan los archivos importados (backend/data/)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


# ── Ventas ──────────────────────────────────────────────────────────────────────

def parse_ventas_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ['fecha', 'producto_id', 'nombre_producto', 'cantidad', 'precio_unitario', 'monto_total']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes: {', '.join(missing)}")
    df['fecha'] = pd.to_datetime(df['fecha'])
    df['cantidad'] = df['cantidad'].astype(int)
    df['precio_unitario'] = df['precio_unitario'].astype(float)
    df['monto_total'] = df['monto_total'].astype(float)
    return df


def import_ventas_rows(df: pd.DataFrame, db: Session) -> tuple[int, list[str]]:
    count = 0
    errores = []
    for idx, row in df.iterrows():
        try:
            db.add(Venta(
                fecha=row['fecha'].to_pydatetime(),
                producto_id=str(row['producto_id']),
                nombre_producto=str(row['nombre_producto']),
                cantidad=int(row['cantidad']),
                precio_unitario=float(row['precio_unitario']),
                monto_total=float(row['monto_total']),
                cliente_id=str(row.get('cliente_id', '')) if pd.notna(row.get('cliente_id')) else None,
                categoria=str(row.get('categoria', '')) if pd.notna(row.get('categoria')) else None,
            ))
            count += 1
        except Exception as e:
            errores.append(f"Fila {idx + 2}: {e}")
    db.commit()
    return count, errores


# ── Gastos ──────────────────────────────────────────────────────────────────────

def parse_gastos_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ['fecha', 'descripcion', 'categoria', 'monto']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes: {', '.join(missing)}")
    df['fecha'] = pd.to_datetime(df['fecha'])
    df['monto'] = df['monto'].astype(float)
    return df


def import_gastos_rows(df: pd.DataFrame, db: Session) -> tuple[int, list[str]]:
    count = 0
    errores = []
    for idx, row in df.iterrows():
        try:
            db.add(Gasto(
                fecha=row['fecha'].to_pydatetime(),
                descripcion=str(row['descripcion']),
                categoria=str(row['categoria']),
                monto=float(row['monto']),
                proveedor_id=str(row.get('proveedor_id', '')) if pd.notna(row.get('proveedor_id')) else None,
                nombre_proveedor=str(row.get('nombre_proveedor', '')) if pd.notna(row.get('nombre_proveedor')) else None,
                tipo_pago=str(row.get('tipo_pago', '')) if pd.notna(row.get('tipo_pago')) else None,
                numero_factura=str(row.get('numero_factura', '')) if pd.notna(row.get('numero_factura')) else None,
                notas=str(row.get('notas', '')) if pd.notna(row.get('notas')) else None,
            ))
            count += 1
        except Exception as e:
            errores.append(f"Fila {idx + 2}: {e}")
    db.commit()
    return count, errores


# ── Inventario (upsert por producto_id) ─────────────────────────────────────────

def parse_inventario_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ['producto_id', 'nombre_producto', 'cantidad_actual']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes: {', '.join(missing)}")
    df['cantidad_actual'] = df['cantidad_actual'].astype(int)
    if 'cantidad_minima' in df.columns:
        df['cantidad_minima'] = df['cantidad_minima'].fillna(0).astype(int)
    if 'precio_compra' in df.columns:
        df['precio_compra'] = pd.to_numeric(df['precio_compra'], errors='coerce')
    if 'precio_venta' in df.columns:
        df['precio_venta'] = pd.to_numeric(df['precio_venta'], errors='coerce')
    return df


def import_inventario_rows(df: pd.DataFrame, db: Session) -> tuple[int, int, list[str]]:
    """Returns (created, updated, errores)."""
    creados = 0
    actualizados = 0
    errores = []
    for idx, row in df.iterrows():
        try:
            producto_id = str(row['producto_id'])
            existing = db.query(Inventario).filter(Inventario.producto_id == producto_id).first()
            fields = dict(
                nombre_producto=str(row['nombre_producto']),
                descripcion=str(row.get('descripcion', '')) if pd.notna(row.get('descripcion')) else None,
                categoria=str(row.get('categoria', '')) if pd.notna(row.get('categoria')) else None,
                cantidad_actual=int(row['cantidad_actual']),
                cantidad_minima=int(row.get('cantidad_minima', 0)) if pd.notna(row.get('cantidad_minima')) else None,
                unidad_medida=str(row.get('unidad_medida', '')) if pd.notna(row.get('unidad_medida')) else None,
                precio_compra=float(row['precio_compra']) if pd.notna(row.get('precio_compra')) else None,
                precio_venta=float(row['precio_venta']) if pd.notna(row.get('precio_venta')) else None,
                proveedor_id=str(row.get('proveedor_id', '')) if pd.notna(row.get('proveedor_id')) else None,
                ubicacion=str(row.get('ubicacion', '')) if pd.notna(row.get('ubicacion')) else None,
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                actualizados += 1
            else:
                db.add(Inventario(producto_id=producto_id, **fields))
                creados += 1
        except Exception as e:
            errores.append(f"Fila {idx + 2}: {e}")
    db.commit()
    return creados, actualizados, errores


# ── Clientes (upsert por cliente_id) ────────────────────────────────────────────

def parse_clientes_df(df: pd.DataFrame) -> pd.DataFrame:
    required = ['cliente_id', 'nombre', 'fecha_registro']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes: {', '.join(missing)}")
    df['fecha_registro'] = pd.to_datetime(df['fecha_registro'])
    if 'activo' in df.columns:
        df['activo'] = df['activo'].fillna(True).astype(bool)
    return df


def import_clientes_rows(df: pd.DataFrame, db: Session) -> tuple[int, int, list[str]]:
    """Returns (created, updated, errores)."""
    creados = 0
    actualizados = 0
    errores = []
    for idx, row in df.iterrows():
        try:
            cliente_id = str(row['cliente_id'])
            existing = db.query(Cliente).filter(Cliente.cliente_id == cliente_id).first()
            fields = dict(
                nombre=str(row['nombre']),
                email=str(row.get('email', '')) if pd.notna(row.get('email')) else None,
                telefono=str(row.get('telefono', '')) if pd.notna(row.get('telefono')) else None,
                direccion=str(row.get('direccion', '')) if pd.notna(row.get('direccion')) else None,
                ciudad=str(row.get('ciudad', '')) if pd.notna(row.get('ciudad')) else None,
                codigo_postal=str(row.get('codigo_postal', '')) if pd.notna(row.get('codigo_postal')) else None,
                rfc=str(row.get('rfc', '')) if pd.notna(row.get('rfc')) else None,
                tipo_cliente=str(row.get('tipo_cliente', '')) if pd.notna(row.get('tipo_cliente')) else None,
                fecha_registro=row['fecha_registro'].to_pydatetime(),
                notas=str(row.get('notas', '')) if pd.notna(row.get('notas')) else None,
                activo=bool(row.get('activo', True)) if pd.notna(row.get('activo')) else True,
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                actualizados += 1
            else:
                db.add(Cliente(cliente_id=cliente_id, **fields))
                creados += 1
        except Exception as e:
            errores.append(f"Fila {idx + 2}: {e}")
    db.commit()
    return creados, actualizados, errores


# ── Auto-watch helpers ───────────────────────────────────────────────────────

def save_and_watch(
    datasource_type: str,
    df: pd.DataFrame,
    db: Session,
    filename: str = "",
    source_type: str = "csv",
    sheet: str = "",
    original_file_content: bytes = None,
    spreadsheet_id: str = "",
    source_name: str = "",
) -> str:
    """
    Guarda la fuente de datos en disco y crea/actualiza el watcher.

    - CSV/Excel:       guarda el archivo en DATA_DIR.
    - Google Sheets:   no hay archivo local; path_str es un placeholder.
    Retorna la ruta del archivo guardado (o un identificador para GSheets).
    """
    import json as _json

    total_rows = len(df)
    now = datetime.now(timezone.utc)

    if source_type == "google_sheets":
        path_str = f"google_sheets:{datasource_type}"
        source_config = _json.dumps({"spreadsheet_id": spreadsheet_id, "sheet": sheet})
        mtime = 0.0
    else:
        ext = ".xlsx" if source_type == "excel" else ".csv"
        base = filename if filename else f"{datasource_type}{ext}"
        dest = DATA_DIR / base

        if original_file_content:
            dest.write_bytes(original_file_content)
        else:
            df.to_csv(dest, index=False)

        path_str = str(dest)
        mtime = os.path.getmtime(path_str)
        source_config = _json.dumps({"sheet": sheet} if sheet else {})

    display_name = source_name or filename or datasource_type

    w = db.query(WatchedFile).filter(WatchedFile.datasource_type == datasource_type).first()
    if w:
        w.file_path = path_str
        w.source_type = source_type
        w.source_config = source_config
        w.source_name = display_name
        w.last_row_count = total_rows
        w.last_mtime = mtime
        w.last_imported_at = now
        w.last_error = None
        w.enabled = True
    else:
        w = WatchedFile(
            datasource_type=datasource_type,
            file_path=path_str,
            source_type=source_type,
            source_config=source_config,
            source_name=display_name,
            enabled=True,
            last_row_count=total_rows,
            last_mtime=mtime,
            last_imported_at=now,
        )
        db.add(w)
    db.commit()
    logger.info(f"[Watcher] Auto-watch: {datasource_type} ({source_type}) -> {path_str}")
    return path_str
