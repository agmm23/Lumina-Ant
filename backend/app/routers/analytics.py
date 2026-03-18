"""
Lumina_Ant - Router de Analytics
Endpoints para análisis de datos, insights de IA y alertas
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db
from app.schemas.schemas import VentasStats, InsightResponse, Alerta as AlertaSchema, MessageResponse
from app.services.analytics_service import AnalyticsService
from app.services.ai_service import AIService
from app.models.models import Venta, Alerta, AlertConfig

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
        
        # Llamar servicio de IA
        ai_service = AIService()
        insights = await ai_service.analyze_sales(ventas_data)
        
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
    tipo: Optional[str] = Query(None, description="Filtrar por tipo: ventas, gastos, inventario"),
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Obtiene lista de alertas

    - solo_no_leidas: Si True, solo retorna alertas no leídas
    - tipo: Filtrar por tipo (ventas, gastos, inventario)
    - limit: Número máximo de alertas a retornar
    """
    # Solo mostrar alertas cuya regla esté habilitada
    enabled_rule_ids = {
        c.rule_id for c in db.query(AlertConfig).filter(AlertConfig.enabled == True).all()
    }

    query = db.query(Alerta).filter(
        Alerta.rule_id.in_(enabled_rule_ids) | Alerta.rule_id.is_(None)
    )

    if solo_no_leidas:
        query = query.filter(Alerta.leida == False)

    if tipo:
        query = query.filter(Alerta.tipo == tipo)

    alertas = query.order_by(Alerta.fecha_creacion.desc()).limit(limit).all()

    logger.info(f"Consultadas {len(alertas)} alertas (no_leidas={solo_no_leidas}, tipo={tipo})")
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


# ── Alert Config ─────────────────────────────────────────────────────────────

RULE_META = {
    "ventas_caida": {
        "label": "Caída de ventas",
        "description": "Ventas del último día caen más de {umbral}% vs promedio ({periodo} días)",
        "tipo": "ventas", "nivel": "warning",
        "params_def": [
            {"key": "umbral", "label": "Porcentaje de caída", "type": "number", "default": 30, "min": 5, "max": 90, "suffix": "%"},
            {"key": "periodo", "label": "Período de comparación", "type": "number", "default": 14, "min": 3, "max": 90, "suffix": "días"},
        ],
    },
    "ventas_criticas": {
        "label": "Ventas críticas",
        "description": "Ventas del último día < ${minimo} con promedio > ${promedio_min}",
        "tipo": "ventas", "nivel": "critical",
        "params_def": [
            {"key": "minimo", "label": "Umbral mínimo de ventas", "type": "number", "default": 100, "min": 0, "max": 10000, "prefix": "$"},
            {"key": "promedio_min", "label": "Promedio mínimo requerido", "type": "number", "default": 200, "min": 0, "max": 10000, "prefix": "$"},
        ],
    },
    "ventas_tendencia": {
        "label": "Tendencia descendente",
        "description": "Ventas cayendo {dias} días consecutivos",
        "tipo": "ventas", "nivel": "warning",
        "params_def": [
            {"key": "dias", "label": "Días consecutivos", "type": "number", "default": 3, "min": 2, "max": 14, "suffix": "días"},
        ],
    },
    "gastos_pico": {
        "label": "Pico de gastos",
        "description": "Gastos del último día > {umbral}% por encima del promedio ({periodo} días)",
        "tipo": "gastos", "nivel": "warning",
        "params_def": [
            {"key": "umbral", "label": "Porcentaje sobre promedio", "type": "number", "default": 50, "min": 10, "max": 200, "suffix": "%"},
            {"key": "periodo", "label": "Período de comparación", "type": "number", "default": 14, "min": 3, "max": 90, "suffix": "días"},
        ],
    },
    "gastos_excesivos": {
        "label": "Gastos excesivos",
        "description": "Gastos del último día > {multiplicador}x el promedio",
        "tipo": "gastos", "nivel": "critical",
        "params_def": [
            {"key": "multiplicador", "label": "Multiplicador del promedio", "type": "number", "default": 2, "min": 1.5, "max": 10, "suffix": "x"},
        ],
    },
    "gastos_tendencia": {
        "label": "Tendencia ascendente",
        "description": "Gastos subiendo {dias} días consecutivos",
        "tipo": "gastos", "nivel": "warning",
        "params_def": [
            {"key": "dias", "label": "Días consecutivos", "type": "number", "default": 3, "min": 2, "max": 14, "suffix": "días"},
        ],
    },
    "inventario_bajo": {
        "label": "Stock bajo",
        "description": "Productos con cantidad actual bajo el mínimo configurado",
        "tipo": "inventario", "nivel": "warning",
        "params_def": [],
    },
    "inventario_sin_stock": {
        "label": "Sin stock",
        "description": "Productos con cantidad actual = 0",
        "tipo": "inventario", "nivel": "critical",
        "params_def": [],
    },
}


import json as _json


def _resolve_description(meta: dict, params: dict) -> str:
    """Interpola parámetros en la descripción de la regla."""
    desc = meta.get("description", "")
    for pd in meta.get("params_def", []):
        key = pd["key"]
        val = params.get(key, pd["default"])
        desc = desc.replace("{" + key + "}", str(val))
    return desc


@router.get("/alert-config")
def get_alert_config(db: Session = Depends(get_db)):
    """Retorna todas las reglas de alerta con su estado y parámetros."""
    configs = {}
    for c in db.query(AlertConfig).all():
        configs[c.rule_id] = {"enabled": c.enabled, "params": _json.loads(c.params) if c.params else {}}
    result = []
    for rule_id, meta in RULE_META.items():
        cfg = configs.get(rule_id, {"enabled": True, "params": {}})
        # Merge defaults con params guardados
        params = {}
        for pd in meta.get("params_def", []):
            params[pd["key"]] = cfg["params"].get(pd["key"], pd["default"])
        result.append({
            "rule_id": rule_id,
            "enabled": cfg["enabled"],
            "label": meta["label"],
            "description": _resolve_description(meta, params),
            "tipo": meta["tipo"],
            "nivel": meta["nivel"],
            "params_def": meta.get("params_def", []),
            "params": params,
        })
    return result


@router.patch("/alert-config/{rule_id}")
def update_alert_rule(rule_id: str, body: dict, db: Session = Depends(get_db)):
    """Actualiza enabled y/o params de una regla de alerta."""
    if rule_id not in RULE_META:
        raise HTTPException(status_code=404, detail=f"Regla '{rule_id}' no encontrada")
    config = db.query(AlertConfig).filter(AlertConfig.rule_id == rule_id).first()
    if not config:
        config = AlertConfig(rule_id=rule_id, enabled=body.get("enabled", True))
        db.add(config)
    if "enabled" in body:
        config.enabled = body["enabled"]
    if "params" in body:
        config.params = _json.dumps(body["params"])
    db.commit()
    return {"rule_id": rule_id, "enabled": config.enabled, "params": _json.loads(config.params) if config.params else {}}


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
