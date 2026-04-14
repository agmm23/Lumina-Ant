"""
Lumina_Ant - Router de Gastos
Endpoints para gestión de gastos: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging

from sqlalchemy import func, text as sa_text

from app.database import get_db
from app.models.models import Gasto
from app.schemas.schemas import (
    Gasto as GastoSchema, GastoCreate, MessageResponse,
    GastosAnalytics, TimeSeriesPoint, CategoryBreakdown, TopItem,
)
from app.services.csv_import import parse_gastos_df, import_gastos_rows, save_and_watch
from app.services.data_reader import create_reader, detect_source_type
from app.services.watcher_service import bump_import_version
from app.auth.dependencies import get_current_user
from app.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gastos", tags=["gastos"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_gastos_csv(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    sheet_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Carga un archivo CSV o Excel con gastos.
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

        df = parse_gastos_df(df)
        db.query(Gasto).filter(Gasto.user_id == current_user.id).delete()
        db.flush()
        gastos_creados, errores = import_gastos_rows(df, db, user_id=current_user.id)
        bump_import_version()

        watched_path = save_and_watch(
            "gastos", df, db, file.filename,
            source_type=source_type,
            sheet=sheet_name or "",
            original_file_content=contents,
            source_name=file.filename or "",
            user_id=current_user.id,
        )

        mensaje = f"Se cargaron {gastos_creados} gastos exitosamente"
        if errores:
            mensaje += f". {len(errores)} registros con errores"
        logger.info(f"Importación completada: {gastos_creados} gastos, {len(errores)} errores")

        return MessageResponse(
            status="success",
            message=mensaje,
            data={"gastos_creados": gastos_creados, "errores": errores[:10] if errores else [], "watched_path": watched_path},
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


@router.get("/analytics/resumen", response_model=GastosAnalytics)
def get_gastos_analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = "dia",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna todos los datos agregados que necesita la página de Gastos.
    Toda la agregación se hace en SQL.
    """
    uid = current_user.id
    filters = [Gasto.user_id == uid]
    if date_from:
        filters.append(Gasto.fecha >= date_from)
    if date_to:
        filters.append(Gasto.fecha <= date_to + " 23:59:59")

    # ── KPIs ──
    kpi = db.query(
        func.coalesce(func.sum(Gasto.monto), 0).label("total"),
        func.count(Gasto.id).label("count"),
    ).filter(*filters).first()

    total_gastos = float(kpi.total)
    num_reg = int(kpi.count)
    promedio = round(total_gastos / num_reg, 2) if num_reg > 0 else 0.0

    # Top categoría (por monto)
    top_cat = db.query(
        func.coalesce(Gasto.categoria, "Sin categoría").label("cat"),
    ).filter(*filters).group_by("cat").order_by(
        func.sum(Gasto.monto).desc()
    ).limit(1).first()

    # Top tipo de pago (por monto)
    top_tp = db.query(
        func.coalesce(Gasto.tipo_pago, "Sin tipo").label("tp"),
    ).filter(*filters).group_by("tp").order_by(
        func.sum(Gasto.monto).desc()
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
                   SUM(monto) AS total
            FROM gastos {where}
            GROUP BY fk ORDER BY fk
        """
    elif group_by == "mes":
        sql = f"""
            SELECT strftime('%Y-%m-01', fecha) AS fk, SUM(monto) AS total
            FROM gastos {where}
            GROUP BY fk ORDER BY fk
        """
    else:
        sql = f"""
            SELECT strftime('%Y-%m-%d', fecha) AS fk, SUM(monto) AS total
            FROM gastos {where}
            GROUP BY fk ORDER BY fk
        """

    serie_rows = db.execute(sa_text(sql), params).fetchall()
    serie_temporal = [TimeSeriesPoint(fecha=r[0], total=round(float(r[1]))) for r in serie_rows]

    # ── Por categoría (top 7) ──
    cat_rows = db.query(
        func.coalesce(Gasto.categoria, "Sin categoría").label("cat"),
        func.sum(Gasto.monto).label("total"),
    ).filter(*filters).group_by("cat").order_by(
        func.sum(Gasto.monto).desc()
    ).limit(7).all()

    # ── Top 5 proveedores ──
    prov_rows = db.query(
        func.coalesce(Gasto.nombre_proveedor, "Sin proveedor").label("prov"),
        func.sum(Gasto.monto).label("total"),
    ).filter(*filters).group_by("prov").order_by(
        func.sum(Gasto.monto).desc()
    ).limit(5).all()

    return GastosAnalytics(
        total_gastos=round(total_gastos, 2),
        num_registros=num_reg,
        gasto_promedio=promedio,
        top_categoria=top_cat.cat if top_cat else "N/A",
        top_tipo_pago=top_tp.tp if top_tp else "N/A",
        serie_temporal=serie_temporal,
        por_categoria=[CategoryBreakdown(categoria=r.cat, total=round(float(r.total))) for r in cat_rows],
        top_proveedores=[
            TopItem(
                nombre=r.prov[:22] + "…" if len(r.prov) > 22 else r.prov,
                monto=round(float(r.total)),
            ) for r in prov_rows
        ],
    )


@router.get("/", response_model=List[GastoSchema])
def get_gastos(
    skip: int = 0,
    limit: int = 15,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene lista de gastos con paginación y filtro de fechas opcionales.
    limit=0 retorna todos los registros.
    """
    query = db.query(Gasto).filter(Gasto.user_id == current_user.id)
    if date_from:
        query = query.filter(Gasto.fecha >= date_from)
    if date_to:
        query = query.filter(Gasto.fecha <= date_to + " 23:59:59")
    query = query.order_by(Gasto.fecha.desc()).offset(skip)
    if limit > 0:
        query = query.limit(limit)
    gastos = query.all()
    logger.info(f"Consultados {len(gastos)} gastos (skip={skip}, limit={limit})")
    return gastos


@router.get("/{gasto_id}", response_model=GastoSchema)
def get_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un gasto específico por su ID
    """
    gasto = db.query(Gasto).filter(Gasto.id == gasto_id, Gasto.user_id == current_user.id).first()

    if not gasto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gasto con ID {gasto_id} no encontrado"
        )

    return gasto


@router.post("/", response_model=GastoSchema)
def create_gasto(
    gasto: GastoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea un nuevo gasto manualmente
    """
    try:
        db_gasto = Gasto(user_id=current_user.id, **gasto.model_dump())
        db.add(db_gasto)
        db.commit()
        db.refresh(db_gasto)

        logger.info(f"Gasto creado: {db_gasto.id}")
        return db_gasto

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando gasto: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando gasto: {str(e)}"
        )


@router.delete("/{gasto_id}", response_model=MessageResponse)
def delete_gasto(
    gasto_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Elimina un gasto por su ID
    """
    gasto = db.query(Gasto).filter(Gasto.id == gasto_id, Gasto.user_id == current_user.id).first()

    if not gasto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gasto con ID {gasto_id} no encontrado"
        )

    db.delete(gasto)
    db.commit()

    logger.info(f"Gasto {gasto_id} eliminado")

    return MessageResponse(
        status="success",
        message=f"Gasto {gasto_id} eliminado exitosamente"
    )


@router.get("/stats/count")
def get_gastos_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el conteo total de gastos del usuario
    """
    count = db.query(Gasto).filter(Gasto.user_id == current_user.id).count()
    return {"total_gastos": count}


@router.get("/stats/total-por-categoria")
def get_gastos_por_categoria(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el total de gastos agrupados por categoría
    """
    result = db.query(
        Gasto.categoria,
        func.sum(Gasto.monto).label('total'),
        func.count(Gasto.id).label('cantidad')
    ).filter(Gasto.user_id == current_user.id).group_by(Gasto.categoria).all()

    gastos_por_categoria = [
        {
            "categoria": cat,
            "total": float(total),
            "cantidad": int(cant)
        }
        for cat, total, cant in result
    ]

    return {
        "status": "success",
        "data": gastos_por_categoria
    }
