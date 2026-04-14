"""
Lumina_Ant - Router de Clientes
Endpoints para gestión de clientes: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging

from sqlalchemy import func

from app.database import get_db
from app.models.models import Cliente
from app.schemas.schemas import Cliente as ClienteSchema, ClienteCreate, ClienteUpdate, MessageResponse, CiudadCount
from app.services.csv_import import parse_clientes_df, import_clientes_rows, save_and_watch
from app.services.data_reader import create_reader, detect_source_type
from app.services.watcher_service import bump_import_version
from app.auth.dependencies import get_current_user
from app.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_clientes_csv(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    sheet_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Carga un archivo CSV o Excel con clientes.
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

        df = parse_clientes_df(df)
        clientes_creados, clientes_actualizados, errores = import_clientes_rows(df, db, user_id=current_user.id)
        bump_import_version()

        watched_path = save_and_watch(
            "clientes", df, db, file.filename,
            source_type=source_type,
            sheet=sheet_name or "",
            original_file_content=contents,
            source_name=file.filename or "",
            user_id=current_user.id,
        )

        mensaje = f"Se procesaron {clientes_creados + clientes_actualizados} clientes: {clientes_creados} creados, {clientes_actualizados} actualizados"
        if errores:
            mensaje += f". {len(errores)} registros con errores"

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
        logger.error(f"Error procesando archivo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivo: {str(e)}"
        )


@router.get("/analytics/resumen")
def get_clientes_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna KPIs agregados de clientes del usuario.
    """
    uid = current_user.id
    total = db.query(func.count(Cliente.id)).filter(Cliente.user_id == uid).scalar()
    activos = db.query(func.count(Cliente.id)).filter(Cliente.user_id == uid, Cliente.activo == True).scalar()

    # Por tipo
    tipo_rows = db.query(
        func.coalesce(Cliente.tipo_cliente, "Sin tipo").label("tipo"),
        func.count(Cliente.id).label("cant"),
    ).filter(Cliente.user_id == uid, Cliente.activo == True).group_by("tipo").all()

    # Por ciudad (top 8)
    ciudad_rows = db.query(
        func.coalesce(Cliente.ciudad, "Sin ciudad").label("ciudad"),
        func.count(Cliente.id).label("cant"),
    ).filter(Cliente.user_id == uid, Cliente.activo == True).group_by("ciudad").order_by(
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
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene lista de clientes con paginación.
    limit=0 retorna todos los registros.
    """
    query = db.query(Cliente).filter(Cliente.user_id == current_user.id)

    if solo_activos:
        query = query.filter(Cliente.activo == True)

    query = query.order_by(Cliente.nombre).offset(skip)
    if limit > 0:
        query = query.limit(limit)
    clientes = query.all()
    logger.info(f"Consultados {len(clientes)} clientes (skip={skip}, limit={limit}, solo_activos={solo_activos})")
    return clientes


@router.get("/{cliente_id}", response_model=ClienteSchema)
def get_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un cliente por su ID (ID numérico de base de datos)
    """
    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.user_id == current_user.id,
    ).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {cliente_id} no encontrado"
        )

    return cliente


@router.get("/buscar/{cliente_id_externo}", response_model=ClienteSchema)
def get_cliente_by_external_id(
    cliente_id_externo: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un cliente por su cliente_id (ID externo/de negocio)
    """
    cliente = db.query(Cliente).filter(
        Cliente.cliente_id == cliente_id_externo,
        Cliente.user_id == current_user.id,
    ).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente {cliente_id_externo} no encontrado"
        )

    return cliente


@router.post("/", response_model=ClienteSchema)
def create_cliente(
    cliente: ClienteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea un nuevo cliente
    """
    existing = db.query(Cliente).filter(
        Cliente.cliente_id == cliente.cliente_id,
        Cliente.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cliente {cliente.cliente_id} ya existe"
        )

    try:
        db_cliente = Cliente(user_id=current_user.id, **cliente.model_dump())
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Actualiza un cliente
    """
    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.user_id == current_user.id,
    ).first()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente con ID {cliente_id} no encontrado"
        )

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
def delete_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Elimina un cliente por su ID
    """
    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.user_id == current_user.id,
    ).first()

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
def desactivar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Desactiva un cliente sin eliminarlo
    """
    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.user_id == current_user.id,
    ).first()

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
def get_clientes_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el conteo total de clientes del usuario
    """
    total = db.query(Cliente).filter(Cliente.user_id == current_user.id).count()
    activos = db.query(Cliente).filter(Cliente.user_id == current_user.id, Cliente.activo == True).count()

    return {
        "total_clientes": total,
        "clientes_activos": activos,
        "clientes_inactivos": total - activos
    }


@router.get("/stats/por-tipo")
def get_clientes_por_tipo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el conteo de clientes agrupados por tipo
    """
    result = db.query(
        Cliente.tipo_cliente,
        func.count(Cliente.id).label('cantidad')
    ).filter(
        Cliente.user_id == current_user.id,
        Cliente.activo == True,
    ).group_by(Cliente.tipo_cliente).all()

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
