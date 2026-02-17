"""
Lumina_Ant - Router de Analytics
Endpoints para análisis de datos, insights de IA y alertas
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.schemas.schemas import VentasStats, InsightResponse, Alerta as AlertaSchema, MessageResponse
from app.services.analytics_service import AnalyticsService
from app.services.claude_service import ClaudeService
from app.models.models import Venta, Alerta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/stats", response_model=VentasStats)
def get_stats(db: Session = Depends(get_db)):
    """
    Obtiene estadísticas básicas de ventas
    
    Retorna:
    - Total de ventas
    - Cantidad de transacciones
    - Ticket promedio
    - Producto más vendido
    - Categoría principal
    """
    try:
        stats = AnalyticsService.calculate_stats(db)
        logger.info("Estadísticas calculadas exitosamente")
        return VentasStats(**stats)
    except Exception as e:
        logger.error(f"Error calculando estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculando estadísticas: {str(e)}"
        )


@router.get("/insights", response_model=InsightResponse)
async def get_insights(db: Session = Depends(get_db)):
    """
    Obtiene insights generados por IA usando Claude
    
    Analiza las ventas y retorna:
    - Resumen ejecutivo
    - Insights accionables
    - Alertas detectadas
    - Recomendaciones
    """
    # Obtener ventas (limitar a últimas 500 para no saturar el API)
    ventas = db.query(Venta).order_by(Venta.fecha.desc()).limit(500).all()
    
    if not ventas:
        logger.warning("No hay ventas para analizar")
        return InsightResponse(
            resumen="No hay datos suficientes para análisis",
            insights=["Carga datos de ventas para obtener insights"],
            alertas=[],
            recomendaciones=["Importa tu primer archivo CSV con ventas"]
        )
    
    try:
        # Convertir a formato para Claude
        ventas_data = [{
            "fecha": v.fecha.isoformat(),
            "producto": v.nombre_producto,
            "producto_id": v.producto_id,
            "cantidad": v.cantidad,
            "monto": v.monto_total,
            "categoria": v.categoria if v.categoria else "Sin categoría"
        } for v in ventas]
        
        # Llamar servicio de Claude
        claude_service = ClaudeService()
        insights = await claude_service.analyze_sales(ventas_data)
        
        logger.info(f"Insights generados para {len(ventas)} ventas")
        return InsightResponse(**insights)
    
    except Exception as e:
        logger.error(f"Error generando insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando insights: {str(e)}"
        )


@router.post("/detect-anomalies", response_model=MessageResponse)
def detect_anomalies(db: Session = Depends(get_db)):
    """
    Detecta anomalías en ventas y genera alertas automáticamente
    
    Compara ventas recientes con promedio histórico y crea alertas si detecta:
    - Caídas significativas (>30%)
    - Ventas muy bajas
    - Tendencias descendentes
    """
    try:
        alertas = AnalyticsService.detect_anomalies(db)
        
        mensaje = f"Análisis completado. {len(alertas)} alerta(s) creada(s)"
        
        alertas_data = [
            {
                "id": a.id,
                "tipo": a.tipo,
                "nivel": a.nivel,
                "mensaje": a.mensaje
            } for a in alertas
        ]
        
        logger.info(f"Detección de anomalías completada: {len(alertas)} alertas")
        
        return MessageResponse(
            status="success",
            message=mensaje,
            data={"alertas": alertas_data}
        )
    
    except Exception as e:
        logger.error(f"Error detectando anomalías: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detectando anomalías: {str(e)}"
        )


@router.get("/alertas", response_model=List[AlertaSchema])
def get_alertas(
    solo_no_leidas: bool = True,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de alertas
    
    - solo_no_leidas: Si True, solo retorna alertas no leídas
    - limit: Número máximo de alertas a retornar
    """
    query = db.query(Alerta)
    
    if solo_no_leidas:
        query = query.filter(Alerta.leida == False)
    
    alertas = query.order_by(Alerta.fecha_creacion.desc()).limit(limit).all()
    
    logger.info(f"Consultadas {len(alertas)} alertas (no_leidas={solo_no_leidas})")
    return alertas


@router.patch("/alertas/{alerta_id}/marcar-leida", response_model=MessageResponse)
def marcar_alerta_leida(alerta_id: int, db: Session = Depends(get_db)):
    """
    Marca una alerta como leída
    """
    alerta = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    
    if not alerta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta con ID {alerta_id} no encontrada"
        )
    
    alerta.leida = True
    db.commit()
    
    logger.info(f"Alerta {alerta_id} marcada como leída")
    
    return MessageResponse(
        status="success",
        message=f"Alerta {alerta_id} marcada como leída"
    )


@router.get("/top-productos")
def get_top_productos(limit: int = 5, db: Session = Depends(get_db)):
    """
    Obtiene los productos más vendidos
    
    - limit: Número de productos a retornar (default: 5)
    """
    try:
        top_productos = AnalyticsService.get_top_products(db, limit)
        
        logger.info(f"Top {limit} productos consultados")
        
        return {
            "status": "success",
            "cantidad": len(top_productos),
            "productos": top_productos
        }
    
    except Exception as e:
        logger.error(f"Error obteniendo top productos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo productos: {str(e)}"
        )
