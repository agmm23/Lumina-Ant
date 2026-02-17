"""
Lumina_Ant - Router de Ventas
Endpoints para gestión de ventas: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
from datetime import datetime
from io import BytesIO
import logging

from app.database import get_db
from app.models.models import Venta
from app.schemas.schemas import Venta as VentaSchema, VentaCreate, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ventas", tags=["ventas"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_ventas_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Carga un archivo CSV con ventas y lo procesa automáticamente
    
    Columnas esperadas:
    - fecha: Fecha de la venta (formato: YYYY-MM-DD o DD/MM/YYYY)
    - producto_id: ID del producto
    - nombre_producto: Nombre del producto
    - cantidad: Cantidad vendida
    - precio_unitario: Precio por unidad
    - monto_total: Monto total de la venta
    - cliente_id (opcional): ID del cliente
    - categoria (opcional): Categoría del producto
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
        required_cols = [
            'fecha', 'producto_id', 'nombre_producto',
            'cantidad', 'precio_unitario', 'monto_total'
        ]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Columnas faltantes en CSV: {', '.join(missing_cols)}"
            )
        
        # Convertir fecha a datetime (probar múltiples formatos)
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
            df['cantidad'] = df['cantidad'].astype(int)
            df['precio_unitario'] = df['precio_unitario'].astype(float)
            df['monto_total'] = df['monto_total'].astype(float)
        except Exception as e:
            logger.error(f"Error convirtiendo números: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datos numéricos inválidos en CSV"
            )
        
        # Insertar registros en la base de datos
        ventas_creadas = 0
        errores = []
        
        for idx, row in df.iterrows():
            try:
                venta = Venta(
                    fecha=row['fecha'].to_pydatetime(),
                    producto_id=str(row['producto_id']),
                    nombre_producto=str(row['nombre_producto']),
                    cantidad=int(row['cantidad']),
                    precio_unitario=float(row['precio_unitario']),
                    monto_total=float(row['monto_total']),
                    cliente_id=str(row.get('cliente_id', '')) if pd.notna(row.get('cliente_id')) else None,
                    categoria=str(row.get('categoria', '')) if pd.notna(row.get('categoria')) else None
                )
                db.add(venta)
                ventas_creadas += 1
            except Exception as e:
                errores.append(f"Fila {idx + 2}: {str(e)}")
                logger.warning(f"Error en fila {idx + 2}: {e}")
        
        db.commit()
        
        mensaje = f"Se cargaron {ventas_creadas} ventas exitosamente"
        if errores:
            mensaje += f". {len(errores)} registros con errores"
        
        logger.info(f"Importación completada: {ventas_creadas} ventas, {len(errores)} errores")
        
        return MessageResponse(
            status="success",
            message=mensaje,
            data={
                "ventas_creadas": ventas_creadas,
                "errores": errores[:10] if errores else []  # Mostrar solo primeros 10 errores
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


@router.get("/", response_model=List[VentaSchema])
def get_ventas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de ventas con paginación
    
    - skip: Número de registros a saltar (para paginación)
    - limit: Número máximo de registros a retornar
    """
    ventas = db.query(Venta).order_by(Venta.fecha.desc()).offset(skip).limit(limit).all()
    logger.info(f"Consultadas {len(ventas)} ventas (skip={skip}, limit={limit})")
    return ventas


@router.get("/{venta_id}", response_model=VentaSchema)
def get_venta(venta_id: int, db: Session = Depends(get_db)):
    """
    Obtiene una venta específica por su ID
    """
    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venta con ID {venta_id} no encontrada"
        )
    
    return venta


@router.delete("/{venta_id}", response_model=MessageResponse)
def delete_venta(venta_id: int, db: Session = Depends(get_db)):
    """
    Elimina una venta por su ID
    """
    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    
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
def get_ventas_count(db: Session = Depends(get_db)):
    """
    Obtiene el conteo total de ventas en la base de datos
    """
    count = db.query(Venta).count()
    return {"total_ventas": count}
