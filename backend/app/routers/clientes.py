"""
Lumina_Ant - Router de Clientes
Endpoints para gestión de clientes: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
from datetime import datetime
from io import BytesIO
import logging

from app.database import get_db
from app.models.models import Cliente
from app.schemas.schemas import Cliente as ClienteSchema, ClienteCreate, ClienteUpdate, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_clientes_csv(
    file: UploadFile = File(...),
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
        # Leer archivo CSV
        contents = await file.read()
        df = pd.read_csv(BytesIO(contents))

        logger.info(f"CSV cargado: {file.filename}, {len(df)} registros")

        # Validar columnas requeridas
        required_cols = ['cliente_id', 'nombre', 'fecha_registro']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Columnas faltantes en CSV: {', '.join(missing_cols)}"
            )

        # Convertir fecha a datetime
        try:
            df['fecha_registro'] = pd.to_datetime(df['fecha_registro'])
        except Exception as e:
            logger.error(f"Error convirtiendo fechas: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha inválido. Use YYYY-MM-DD o DD/MM/YYYY"
            )

        # Convertir activo a booleano si existe
        if 'activo' in df.columns:
            df['activo'] = df['activo'].fillna(True).astype(bool)

        # Insertar o actualizar registros en la base de datos
        clientes_creados = 0
        clientes_actualizados = 0
        errores = []

        for idx, row in df.iterrows():
            try:
                cliente_id = str(row['cliente_id'])

                # Verificar si ya existe
                existing = db.query(Cliente).filter(Cliente.cliente_id == cliente_id).first()

                if existing:
                    # Actualizar
                    existing.nombre = str(row['nombre'])
                    existing.email = str(row.get('email', '')) if pd.notna(row.get('email')) else None
                    existing.telefono = str(row.get('telefono', '')) if pd.notna(row.get('telefono')) else None
                    existing.direccion = str(row.get('direccion', '')) if pd.notna(row.get('direccion')) else None
                    existing.ciudad = str(row.get('ciudad', '')) if pd.notna(row.get('ciudad')) else None
                    existing.codigo_postal = str(row.get('codigo_postal', '')) if pd.notna(row.get('codigo_postal')) else None
                    existing.rfc = str(row.get('rfc', '')) if pd.notna(row.get('rfc')) else None
                    existing.tipo_cliente = str(row.get('tipo_cliente', '')) if pd.notna(row.get('tipo_cliente')) else None
                    existing.fecha_registro = row['fecha_registro'].to_pydatetime()
                    existing.notas = str(row.get('notas', '')) if pd.notna(row.get('notas')) else None
                    existing.activo = bool(row.get('activo', True)) if pd.notna(row.get('activo')) else True
                    clientes_actualizados += 1
                else:
                    # Crear nuevo
                    cliente = Cliente(
                        cliente_id=cliente_id,
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
                        activo=bool(row.get('activo', True)) if pd.notna(row.get('activo')) else True
                    )
                    db.add(cliente)
                    clientes_creados += 1

            except Exception as e:
                errores.append(f"Fila {idx + 2}: {str(e)}")
                logger.warning(f"Error en fila {idx + 2}: {e}")

        db.commit()

        mensaje = f"Se procesaron {clientes_creados + clientes_actualizados} clientes: {clientes_creados} creados, {clientes_actualizados} actualizados"
        if errores:
            mensaje += f". {len(errores)} registros con errores"

        logger.info(f"Importación completada: {clientes_creados} creados, {clientes_actualizados} actualizados, {len(errores)} errores")

        return MessageResponse(
            status="success",
            message=mensaje,
            data={
                "clientes_creados": clientes_creados,
                "clientes_actualizados": clientes_actualizados,
                "errores": errores[:10] if errores else []
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error procesando CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando archivo CSV: {str(e)}"
        )


@router.get("/", response_model=List[ClienteSchema])
def get_clientes(
    skip: int = 0,
    limit: int = 100,
    solo_activos: bool = True,
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de clientes con paginación

    - skip: Número de registros a saltar
    - limit: Número máximo de registros a retornar
    - solo_activos: Si True, solo retorna clientes activos
    """
    query = db.query(Cliente)

    if solo_activos:
        query = query.filter(Cliente.activo == True)

    clientes = query.order_by(Cliente.nombre).offset(skip).limit(limit).all()
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
