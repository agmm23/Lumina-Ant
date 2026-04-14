"""
Lumina_Ant - Router de Ventas
Endpoints para gestión de ventas: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging

from sqlalchemy import func, text as sa_text

from app.database import get_db
from app.models.models import Venta
from app.schemas.schemas import (
    Venta as VentaSchema, VentaCreate, MessageResponse,
    VentasAnalytics, TimeSeriesPoint, CategoryBreakdown, TopItem,
)
from app.services.csv_import import parse_ventas_df, import_ventas_rows, save_and_watch
from app.services.data_reader import create_reader, detect_source_type
from app.services.watcher_service import bump_import_version
from app.auth.dependencies import get_current_user
from app.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ventas", tags=["ventas"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_ventas_csv(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    sheet_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Carga un archivo CSV o Excel con ventas.
    Para Excel, usar sheet_name para especificar la hoja.
    """
    source_type = detect_source_type(file.filename or "")
    try:
        contents = await file.read()
        reader = create_reader(source_type, contents)
        df = reader.read(sheet=sheet_name or None)
        logger.info(f"Archivo cargado: {file.filename} ({source_type}), {len(df)} registros")

        if column_mapping:
            mapping = json.loads(column_mapping)
            df = df.rename(columns=mapping)

        df = parse_ventas_df(df)
        db.query(Venta).filter(Venta.user_id == current_user.id).delete()
        db.flush()
        ventas_creadas, errores = import_ventas_rows(df, db, user_id=current_user.id)
        bump_import_version()

        watched_path = save_and_watch(
            "ventas", df, db, file.filename,
            source_type=source_type,
            sheet=sheet_name or "",
            original_file_content=contents,
            source_name=file.filename or "",
            user_id=current_user.id,
        )

        mensaje = f"Se cargaron {ventas_creadas} ventas exitosamente"
        if errores:
            mensaje += f". {len(errores)} registros con errores"

        return MessageResponse(
            status="success",
            message=mensaje,
            data={"ventas_creadas": ventas_creadas, "errores": errores[:10] if errores else [], "watched_path": watched_path},
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error procesando archivo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivo: {str(e)}"
        )


@router.get("/analytics/resumen", response_model=VentasAnalytics)
def get_ventas_analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = "dia",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna todos los datos agregados que necesita la página de Ventas.
    Toda la agregación se hace en SQL — no se cargan registros crudos en memoria.
    """
    uid = current_user.id
    filters = [Venta.user_id == uid]
    if date_from:
        filters.append(Venta.fecha >= date_from)
    if date_to:
        filters.append(Venta.fecha <= date_to + " 23:59:59")

    # ── KPIs ──
    kpi = db.query(
        func.coalesce(func.sum(Venta.monto_total), 0).label("total"),
        func.count(Venta.id).label("count"),
    ).filter(*filters).first()

    total_ventas = float(kpi.total)
    num_tx = int(kpi.count)
    ticket = round(total_ventas / num_tx, 2) if num_tx > 0 else 0.0

    # Top producto (por cantidad)
    top_prod = db.query(
        Venta.nombre_producto,
    ).filter(*filters).group_by(
        Venta.nombre_producto
    ).order_by(func.sum(Venta.cantidad).desc()).limit(1).first()

    # Top categoría (por monto)
    top_cat = db.query(
        func.coalesce(Venta.categoria, "Sin categoría").label("cat"),
    ).filter(*filters).group_by("cat").order_by(
        func.sum(Venta.monto_total).desc()
    ).limit(1).first()

    # ── Serie temporal ──
    params = {"uid": uid}
    if date_from:
        params["df"] = date_from
    if date_to:
        params["dt"] = date_to + " 23:59:59"

    where = "WHERE user_id = :uid"
    if date_from:
        where += " AND fecha >= :df"
    if date_to:
        where += " AND fecha <= :dt"

    if group_by == "semana":
        sql = f"""
            SELECT date(fecha, '-' || ((CAST(strftime('%w', fecha) AS INTEGER) + 6) % 7) || ' days') AS fk,
                   SUM(monto_total) AS total
            FROM ventas {where}
            GROUP BY fk ORDER BY fk
        """
    elif group_by == "mes":
        sql = f"""
            SELECT strftime('%Y-%m-01', fecha) AS fk, SUM(monto_total) AS total
            FROM ventas {where}
            GROUP BY fk ORDER BY fk
        """
    else:
        sql = f"""
            SELECT strftime('%Y-%m-%d', fecha) AS fk, SUM(monto_total) AS total
            FROM ventas {where}
            GROUP BY fk ORDER BY fk
        """

    serie_rows = db.execute(sa_text(sql), params).fetchall()
    serie_temporal = [TimeSeriesPoint(fecha=r[0], total=round(float(r[1]))) for r in serie_rows]

    # ── Por categoría (top 7) ──
    cat_rows = db.query(
        func.coalesce(Venta.categoria, "Sin categoría").label("cat"),
        func.sum(Venta.monto_total).label("total"),
    ).filter(*filters).group_by("cat").order_by(
        func.sum(Venta.monto_total).desc()
    ).limit(7).all()

    # ── Top 5 productos ──
    prod_rows = db.query(
        Venta.nombre_producto,
        func.sum(Venta.monto_total).label("total"),
    ).filter(*filters).group_by(
        Venta.nombre_producto
    ).order_by(func.sum(Venta.monto_total).desc()).limit(5).all()

    return VentasAnalytics(
        total_ventas=round(total_ventas, 2),
        num_transacciones=num_tx,
        ticket_promedio=ticket,
        top_producto=top_prod.nombre_producto if top_prod else "N/A",
        top_categoria=top_cat.cat if top_cat else "N/A",
        serie_temporal=serie_temporal,
        por_categoria=[CategoryBreakdown(categoria=r.cat, total=round(float(r.total))) for r in cat_rows],
        top_productos=[
            TopItem(
                nombre=r.nombre_producto[:22] + "…" if len(r.nombre_producto) > 22 else r.nombre_producto,
                monto=round(float(r.total)),
            ) for r in prod_rows
        ],
    )


@router.get("/", response_model=List[VentaSchema])
def get_ventas(
    skip: int = 0,
    limit: int = 15,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene lista de ventas con paginación y filtro de fechas opcionales.
    limit=0 retorna todos los registros.
    """
    query = db.query(Venta).filter(Venta.user_id == current_user.id)
    if date_from:
        query = query.filter(Venta.fecha >= date_from)
    if date_to:
        query = query.filter(Venta.fecha <= date_to + " 23:59:59")
    query = query.order_by(Venta.fecha.desc()).offset(skip)
    if limit > 0:
        query = query.limit(limit)
    ventas = query.all()
    logger.info(f"Consultadas {len(ventas)} ventas (skip={skip}, limit={limit})")
    return ventas


@router.get("/{venta_id}", response_model=VentaSchema)
def get_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene una venta específica por su ID
    """
    venta = db.query(Venta).filter(Venta.id == venta_id, Venta.user_id == current_user.id).first()

    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {venta_id} no encontrada"
        )

    return venta


@router.delete("/{venta_id}", response_model=MessageResponse)
def delete_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Elimina una venta por su ID
    """
    venta = db.query(Venta).filter(Venta.id == venta_id, Venta.user_id == current_user.id).first()

    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {venta_id} no encontrada"
        )

    db.delete(venta)
    db.commit()

    logger.info(f"Venta {venta_id} eliminada")

    return MessageResponse(
        status="success",
        message=f"Venta {venta_id} eliminada exitosamente"
    )


@router.get("/stats/count")
def get_ventas_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el conteo total de ventas del usuario
    """
    count = db.query(Venta).filter(Venta.user_id == current_user.id).count()
    return {"total_ventas": count}
