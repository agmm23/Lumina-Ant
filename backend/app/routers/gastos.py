"""
Lumina_Ant - Router de Gastos
Endpoints para gestión de gastos: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
from datetime import datetime
from io import BytesIO
import logging

from app.database import get_db
from app.models.models import Gasto
from app.schemas.schemas import Gasto as GastoSchema, GastoCreate, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gastos", tags=["gastos"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_gastos_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Carga un archivo CSV con gastos y lo procesa automáticamente

    Columnas esperadas:
    - fecha: Fecha del gasto (formato: YYYY-MM-DD o DD/MM/YYYY)
    - descripcion: Descripción del gasto
    - categoria: Categoría del gasto
    - monto: Monto del gasto
    - proveedor_id (opcional): ID del proveedor
    - nombre_proveedor (opcional): Nombre del proveedor
    - tipo_pago (opcional): Tipo de pago
    - numero_factura (opcional): Número de factura
    - notas (opcional): Notas adicionales
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
        required_cols = ['fecha', 'descripcion', 'categoria', 'monto']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Columnas faltantes en CSV: {', '.join(missing_cols)}"
            )

        # Convertir fecha a datetime
        try:
            df['fecha'] = pd.to_datetime(df['fecha'])
        except Exception as e:
            logger.error(f"Error convirtiendo fechas: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha inválido. Use YYYY-MM-DD o DD/MM/YYYY"
            )

        # Validar datos numéricos
        try:
            df['monto'] = df['monto'].astype(float)
        except Exception as e:
            logger.error(f"Error convirtiendo monto: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Monto inválido en CSV"
            )

        # Insertar registros en la base de datos
        gastos_creados = 0
        errores = []

        for idx, row in df.iterrows():
            try:
                gasto = Gasto(
                    fecha=row['fecha'].to_pydatetime(),
                    descripcion=str(row['descripcion']),
                    categoria=str(row['categoria']),
                    monto=float(row['monto']),
                    proveedor_id=str(row.get('proveedor_id', '')) if pd.notna(row.get('proveedor_id')) else None,
                    nombre_proveedor=str(row.get('nombre_proveedor', '')) if pd.notna(row.get('nombre_proveedor')) else None,
                    tipo_pago=str(row.get('tipo_pago', '')) if pd.notna(row.get('tipo_pago')) else None,
                    numero_factura=str(row.get('numero_factura', '')) if pd.notna(row.get('numero_factura')) else None,
                    notas=str(row.get('notas', '')) if pd.notna(row.get('notas')) else None
                )
                db.add(gasto)
                gastos_creados += 1
            except Exception as e:
                errores.append(f"Fila {idx + 2}: {str(e)}")
                logger.warning(f"Error en fila {idx + 2}: {e}")

        db.commit()

        mensaje = f"Se cargaron {gastos_creados} gastos exitosamente"
        if errores:
            mensaje += f". {len(errores)} registros con errores"

        logger.info(f"Importación completada: {gastos_creados} gastos, {len(errores)} errores")

        return MessageResponse(
            status="success",
            message=mensaje,
            data={
                "gastos_creados": gastos_creados,
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


@router.get("/", response_model=List[GastoSchema])
def get_gastos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de gastos con paginación

    - skip: Número de registros a saltar
    - limit: Número máximo de registros a retornar
    """
    gastos = db.query(Gasto).order_by(Gasto.fecha.desc()).offset(skip).limit(limit).all()
    logger.info(f"Consultados {len(gastos)} gastos (skip={skip}, limit={limit})")
    return gastos


@router.get("/{gasto_id}", response_model=GastoSchema)
def get_gasto(gasto_id: int, db: Session = Depends(get_db)):
    """
    Obtiene un gasto específico por su ID
    """
    gasto = db.query(Gasto).filter(Gasto.id == gasto_id).first()

    if not gasto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gasto con ID {gasto_id} no encontrado"
        )

    return gasto


@router.post("/", response_model=GastoSchema)
def create_gasto(gasto: GastoCreate, db: Session = Depends(get_db)):
    """
    Crea un nuevo gasto manualmente
    """
    try:
        db_gasto = Gasto(**gasto.model_dump())
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
def delete_gasto(gasto_id: int, db: Session = Depends(get_db)):
    """
    Elimina un gasto por su ID
    """
    gasto = db.query(Gasto).filter(Gasto.id == gasto_id).first()

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
def get_gastos_count(db: Session = Depends(get_db)):
    """
    Obtiene el conteo total de gastos en la base de datos
    """
    count = db.query(Gasto).count()
    return {"total_gastos": count}


@router.get("/stats/total-por-categoria")
def get_gastos_por_categoria(db: Session = Depends(get_db)):
    """
    Obtiene el total de gastos agrupados por categoría
    """
    from sqlalchemy import func

    result = db.query(
        Gasto.categoria,
        func.sum(Gasto.monto).label('total'),
        func.count(Gasto.id).label('cantidad')
    ).group_by(Gasto.categoria).all()

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
