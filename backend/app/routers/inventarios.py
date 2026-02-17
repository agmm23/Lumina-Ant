"""
Lumina_Ant - Router de Inventarios
Endpoints para gestión de inventario: CRUD y carga de archivos CSV
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
from datetime import datetime
from io import BytesIO
import logging

from app.database import get_db
from app.models.models import Inventario
from app.schemas.schemas import Inventario as InventarioSchema, InventarioCreate, InventarioUpdate, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventarios", tags=["inventarios"])


@router.post("/upload-csv", response_model=MessageResponse)
async def upload_inventarios_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Carga un archivo CSV con inventario y lo procesa automáticamente

    Columnas esperadas:
    - producto_id: ID único del producto
    - nombre_producto: Nombre del producto
    - descripcion (opcional): Descripción del producto
    - categoria (opcional): Categoría del producto
    - cantidad_actual: Cantidad en stock
    - cantidad_minima (opcional): Cantidad mínima para alerta
    - unidad_medida (opcional): Unidad de medida
    - precio_compra (opcional): Precio de compra
    - precio_venta (opcional): Precio de venta
    - proveedor_id (opcional): ID del proveedor
    - ubicacion (opcional): Ubicación en almacén
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
        required_cols = ['producto_id', 'nombre_producto', 'cantidad_actual']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Columnas faltantes en CSV: {', '.join(missing_cols)}"
            )

        # Validar datos numéricos
        try:
            df['cantidad_actual'] = df['cantidad_actual'].astype(int)
            if 'cantidad_minima' in df.columns:
                df['cantidad_minima'] = df['cantidad_minima'].fillna(0).astype(int)
            if 'precio_compra' in df.columns:
                df['precio_compra'] = pd.to_numeric(df['precio_compra'], errors='coerce')
            if 'precio_venta' in df.columns:
                df['precio_venta'] = pd.to_numeric(df['precio_venta'], errors='coerce')
        except Exception as e:
            logger.error(f"Error convirtiendo números: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datos numéricos inválidos en CSV"
            )

        # Insertar o actualizar registros en la base de datos
        items_creados = 0
        items_actualizados = 0
        errores = []

        for idx, row in df.iterrows():
            try:
                producto_id = str(row['producto_id'])

                # Verificar si ya existe
                existing = db.query(Inventario).filter(Inventario.producto_id == producto_id).first()

                if existing:
                    # Actualizar
                    existing.nombre_producto = str(row['nombre_producto'])
                    existing.descripcion = str(row.get('descripcion', '')) if pd.notna(row.get('descripcion')) else None
                    existing.categoria = str(row.get('categoria', '')) if pd.notna(row.get('categoria')) else None
                    existing.cantidad_actual = int(row['cantidad_actual'])
                    existing.cantidad_minima = int(row.get('cantidad_minima', 0)) if pd.notna(row.get('cantidad_minima')) else None
                    existing.unidad_medida = str(row.get('unidad_medida', '')) if pd.notna(row.get('unidad_medida')) else None
                    existing.precio_compra = float(row['precio_compra']) if pd.notna(row.get('precio_compra')) else None
                    existing.precio_venta = float(row['precio_venta']) if pd.notna(row.get('precio_venta')) else None
                    existing.proveedor_id = str(row.get('proveedor_id', '')) if pd.notna(row.get('proveedor_id')) else None
                    existing.ubicacion = str(row.get('ubicacion', '')) if pd.notna(row.get('ubicacion')) else None
                    items_actualizados += 1
                else:
                    # Crear nuevo
                    inventario = Inventario(
                        producto_id=producto_id,
                        nombre_producto=str(row['nombre_producto']),
                        descripcion=str(row.get('descripcion', '')) if pd.notna(row.get('descripcion')) else None,
                        categoria=str(row.get('categoria', '')) if pd.notna(row.get('categoria')) else None,
                        cantidad_actual=int(row['cantidad_actual']),
                        cantidad_minima=int(row.get('cantidad_minima', 0)) if pd.notna(row.get('cantidad_minima')) else None,
                        unidad_medida=str(row.get('unidad_medida', '')) if pd.notna(row.get('unidad_medida')) else None,
                        precio_compra=float(row['precio_compra']) if pd.notna(row.get('precio_compra')) else None,
                        precio_venta=float(row['precio_venta']) if pd.notna(row.get('precio_venta')) else None,
                        proveedor_id=str(row.get('proveedor_id', '')) if pd.notna(row.get('proveedor_id')) else None,
                        ubicacion=str(row.get('ubicacion', '')) if pd.notna(row.get('ubicacion')) else None
                    )
                    db.add(inventario)
                    items_creados += 1

            except Exception as e:
                errores.append(f"Fila {idx + 2}: {str(e)}")
                logger.warning(f"Error en fila {idx + 2}: {e}")

        db.commit()

        mensaje = f"Se procesaron {items_creados + items_actualizados} items: {items_creados} creados, {items_actualizados} actualizados"
        if errores:
            mensaje += f". {len(errores)} registros con errores"

        logger.info(f"Importación completada: {items_creados} creados, {items_actualizados} actualizados, {len(errores)} errores")

        return MessageResponse(
            status="success",
            message=mensaje,
            data={
                "items_creados": items_creados,
                "items_actualizados": items_actualizados,
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


@router.get("/", response_model=List[InventarioSchema])
def get_inventarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de items del inventario con paginación

    - skip: Número de registros a saltar
    - limit: Número máximo de registros a retornar
    """
    items = db.query(Inventario).order_by(Inventario.nombre_producto).offset(skip).limit(limit).all()
    logger.info(f"Consultados {len(items)} items de inventario (skip={skip}, limit={limit})")
    return items


@router.get("/{inventario_id}", response_model=InventarioSchema)
def get_inventario(inventario_id: int, db: Session = Depends(get_db)):
    """
    Obtiene un item del inventario por su ID
    """
    item = db.query(Inventario).filter(Inventario.id == inventario_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item de inventario con ID {inventario_id} no encontrado"
        )

    return item


@router.get("/producto/{producto_id}", response_model=InventarioSchema)
def get_inventario_by_producto(producto_id: str, db: Session = Depends(get_db)):
    """
    Obtiene un item del inventario por su producto_id
    """
    item = db.query(Inventario).filter(Inventario.producto_id == producto_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto {producto_id} no encontrado en inventario"
        )

    return item


@router.post("/", response_model=InventarioSchema)
def create_inventario(inventario: InventarioCreate, db: Session = Depends(get_db)):
    """
    Crea un nuevo item de inventario
    """
    # Verificar que no exista el producto_id
    existing = db.query(Inventario).filter(Inventario.producto_id == inventario.producto_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Producto {inventario.producto_id} ya existe en inventario"
        )

    try:
        db_inventario = Inventario(**inventario.model_dump())
        db.add(db_inventario)
        db.commit()
        db.refresh(db_inventario)

        logger.info(f"Item de inventario creado: {db_inventario.id}")
        return db_inventario

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando item de inventario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando item de inventario: {str(e)}"
        )


@router.patch("/{inventario_id}", response_model=InventarioSchema)
def update_inventario(
    inventario_id: int,
    inventario_update: InventarioUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza un item del inventario
    """
    item = db.query(Inventario).filter(Inventario.id == inventario_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item de inventario con ID {inventario_id} no encontrado"
        )

    # Actualizar solo los campos proporcionados
    update_data = inventario_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    try:
        db.commit()
        db.refresh(item)
        logger.info(f"Item de inventario {inventario_id} actualizado")
        return item

    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando item de inventario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando item de inventario: {str(e)}"
        )


@router.delete("/{inventario_id}", response_model=MessageResponse)
def delete_inventario(inventario_id: int, db: Session = Depends(get_db)):
    """
    Elimina un item del inventario por su ID
    """
    item = db.query(Inventario).filter(Inventario.id == inventario_id).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item de inventario con ID {inventario_id} no encontrado"
        )

    db.delete(item)
    db.commit()

    logger.info(f"Item de inventario {inventario_id} eliminado")

    return MessageResponse(
        status="success",
        message=f"Item de inventario {inventario_id} eliminado exitosamente"
    )


@router.get("/stats/count")
def get_inventarios_count(db: Session = Depends(get_db)):
    """
    Obtiene el conteo total de items en inventario
    """
    count = db.query(Inventario).count()
    return {"total_items": count}


@router.get("/stats/bajo-stock")
def get_items_bajo_stock(db: Session = Depends(get_db)):
    """
    Obtiene items con stock bajo (cantidad_actual <= cantidad_minima)
    """
    items = db.query(Inventario).filter(
        Inventario.cantidad_minima.isnot(None),
        Inventario.cantidad_actual <= Inventario.cantidad_minima
    ).all()

    items_bajo_stock = [
        {
            "id": item.id,
            "producto_id": item.producto_id,
            "nombre_producto": item.nombre_producto,
            "cantidad_actual": item.cantidad_actual,
            "cantidad_minima": item.cantidad_minima,
            "categoria": item.categoria
        }
        for item in items
    ]

    return {
        "status": "success",
        "cantidad_items": len(items_bajo_stock),
        "items": items_bajo_stock
    }


@router.get("/stats/valor-inventario")
def get_valor_inventario(db: Session = Depends(get_db)):
    """
    Calcula el valor total del inventario (precio_venta * cantidad_actual)
    """
    from sqlalchemy import func

    # Valor total a precio de venta
    result = db.query(
        func.sum(Inventario.cantidad_actual * Inventario.precio_venta).label('valor_total')
    ).filter(Inventario.precio_venta.isnot(None)).first()

    valor_total = float(result.valor_total) if result.valor_total else 0.0

    # Valor total a precio de compra
    result_compra = db.query(
        func.sum(Inventario.cantidad_actual * Inventario.precio_compra).label('costo_total')
    ).filter(Inventario.precio_compra.isnot(None)).first()

    costo_total = float(result_compra.costo_total) if result_compra.costo_total else 0.0

    return {
        "status": "success",
        "valor_inventario_venta": valor_total,
        "costo_inventario": costo_total,
        "margen_potencial": valor_total - costo_total
    }
