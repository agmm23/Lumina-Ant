"""
Lumina_Ant - Router de Clientes
Endpoints para gestión de clientes: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
from datetime import datetime
from io import BytesIO
import json
import logging

from sqlalchemy import func

from app.database import get_db
from app.models.models import Cliente
from app.schemas.schemas import Cliente as ClienteSchema, ClienteCreate, ClienteUpdate, MessageResponse, CiudadCount
from app.services.csv_import import parse_clientes_df, import_clientes_rows, save_and_watch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_clientes_csv(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Carga un archivo CSV con clientes y lo procesa automáticamente

    Columnas esperadas:
    - cliente_id: ID único del cliente
    - nombre: Nombre del cliente
    - email (opcional): Email del cliente
    - telefono (opcional): Teléfono
    - direccion (opcional): Dirección
    - ciudad (opcional): Ciudad
    - codigo_postal (opcional): Código postal
    - rfc (opcional): RFC
    - tipo_cliente (opcional): Tipo de cliente
    - fecha_registro: Fecha de registro (formato: YYYY-MM-DD)
    - notas (opcional): Notas adicionales
    - activo (opcional): Si el cliente está activo (true/false)
    """

    # Validar extensión del archivo
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos CSV"
        )

    try:
        contents = await file.read()
        df = pd.read_csv(BytesIO(contents))
        logger.info(f"CSV cargado: {file.filename}, {len(df)} registros")

        if column_mapping:
            mapping = json.loads(column_mapping)
            df = df.rename(columns=mapping)

        df = parse_clientes_df(df)
        clientes_creados, clientes_actualizados, errores = import_clientes_rows(df, db)

        watched_path = save_and_watch("clientes", df, db, file.filename)

        mensaje = f"Se procesaron {clientes_creados + clientes_actualizados} clientes: {clientes_creados} creados, {clientes_actualizados} actualizados"
        if errores:
            mensaje += f". {len(errores)} registros con errores"
        logger.info(f"Importación completada: {clientes_creados} creados, {clientes_actualizados} actualizados, {len(errores)} errores")

        return MessageResponse(
            status="success",
            message=mensaje,
            data={"clientes_creados": clientes_creados, "clientes_actualizados": clientes_actualizados, "errores": errores[:10] if errores else [], "watched_path": watched_path},
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error procesando CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivo CSV: {str(e)}"
        )


@router.get("/analytics/resumen")
def get_clientes_analytics(db: Session = Depends(get_db)):
    """
    Retorna KPIs agregados de clientes.
    """
    total = db.query(func.count(Cliente.id)).scalar()
    activos = db.query(func.count(Cliente.id)).filter(Cliente.activo == True).scalar()

    # Por tipo
    tipo_rows = db.query(
        func.coalesce(Cliente.tipo_cliente, "Sin tipo").label("tipo"),
        func.count(Cliente.id).label("cant"),
    ).filter(Cliente.activo == True).group_by("tipo").all()

    # Por ciudad (top 8)
    ciudad_rows = db.query(
        func.coalesce(Cliente.ciudad, "Sin ciudad").label("ciudad"),
        func.count(Cliente.id).label("cant"),
    ).filter(Cliente.activo == True).group_by("ciudad").order_by(
        func.count(Cliente.id).desc()
    ).limit(8).all()

    return {
        "total_clientes": int(total),
        "clientes_activos": int(activos),
        "clientes_inactivos": int(total) - int(activos),
        "por_tipo": [{"tipo": r.tipo, "cantidad": int(r.cant)} for r in tipo_rows],
        "por_ciudad": [CiudadCount(ciudad=r.ciudad, cantidad=int(r.cant)) for r in ciudad_rows],
    }


@router.get("/", response_model=List[ClienteSchema])
def get_clientes(
    skip: int = 0,
    limit: int = 0,
    solo_activos: bool = True,
    db: Session = Depends(get_db),
):
    """
    Obtiene lista de clientes con paginación.
    limit=0 retorna todos los registros.
    """
    query = db.query(Cliente)

    if solo_activos:
        query = query.filter(Cliente.activo == True)

    query = query.order_by(Cliente.nombre).offset(skip)
    if limit > 0:
        query = query.limit(limit)
    clientes = query.all()
    logger.info(f"Consultados {len(clientes)} clientes (skip={skip}, limit={limit}, solo_activos={solo_activos})")
    return clientes


@router.get("/{cliente_id}", response_model=ClienteSchema)
def get_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """
    Obtiene un cliente por su ID (ID numérico de base de datos)
    """
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {cliente_id} no encontrado"
        )

    return cliente


@router.get("/buscar/{cliente_id_externo}", response_model=ClienteSchema)
def get_cliente_by_external_id(cliente_id_externo: str, db: Session = Depends(get_db)):
    """
    Obtiene un cliente por su cliente_id (ID externo/de negocio)
    """
    cliente = db.query(Cliente).filter(Cliente.cliente_id == cliente_id_externo).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {cliente_id_externo} no encontrado"
        )

    return cliente


@router.post("/", response_model=ClienteSchema)
def create_cliente(cliente: ClienteCreate, db: Session = Depends(get_db)):
    """
    Crea un nuevo cliente
    """
    # Verificar que no exista el cliente_id
    existing = db.query(Cliente).filter(Cliente.cliente_id == cliente.cliente_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cliente {cliente.cliente_id} ya existe"
        )

    try:
        db_cliente = Cliente(**cliente.model_dump())
        db.add(db_cliente)
        db.commit()
        db.refresh(db_cliente)

        logger.info(f"Cliente creado: {db_cliente.id}")
        return db_cliente

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando cliente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando cliente: {str(e)}"
        )


@router.patch("/{cliente_id}", response_model=ClienteSchema)
def update_cliente(
    cliente_id: int,
    cliente_update: ClienteUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza un cliente
    """
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {cliente_id} no encontrado"
        )

    # Actualizar solo los campos proporcionados
    update_data = cliente_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cliente, key, value)

    try:
        db.commit()
        db.refresh(cliente)
        logger.info(f"Cliente {cliente_id} actualizado")
        return cliente

    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando cliente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando cliente: {str(e)}"
        )


@router.delete("/{cliente_id}", response_model=MessageResponse)
def delete_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """
    Elimina un cliente por su ID
    """
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {cliente_id} no encontrado"
        )

    db.delete(cliente)
    db.commit()

    logger.info(f"Cliente {cliente_id} eliminado")

    return MessageResponse(
        status="success",
        message=f"Cliente {cliente_id} eliminado exitosamente"
    )


@router.patch("/{cliente_id}/desactivar", response_model=MessageResponse)
def desactivar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """
    Desactiva un cliente sin eliminarlo
    """
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {cliente_id} no encontrado"
        )

    cliente.activo = False
    db.commit()

    logger.info(f"Cliente {cliente_id} desactivado")

    return MessageResponse(
        status="success",
        message=f"Cliente {cliente_id} desactivado exitosamente"
    )


@router.get("/stats/count")
def get_clientes_count(db: Session = Depends(get_db)):
    """
    Obtiene el conteo total de clientes
    """
    total = db.query(Cliente).count()
    activos = db.query(Cliente).filter(Cliente.activo == True).count()

    return {
        "total_clientes": total,
        "clientes_activos": activos,
        "clientes_inactivos": total - activos
    }


@router.get("/stats/por-tipo")
def get_clientes_por_tipo(db: Session = Depends(get_db)):
    """
    Obtiene el conteo de clientes agrupados por tipo
    """
    from sqlalchemy import func

    result = db.query(
        Cliente.tipo_cliente,
        func.count(Cliente.id).label('cantidad')
    ).filter(Cliente.activo == True).group_by(Cliente.tipo_cliente).all()

    clientes_por_tipo = [
        {
            "tipo": tipo if tipo else "Sin tipo",
            "cantidad": int(cant)
        }
        for tipo, cant in result
    ]

    return {
        "status": "success",
        "data": clientes_por_tipo
    }
