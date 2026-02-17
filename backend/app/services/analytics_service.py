"""
Lumina_Ant - Servicio de Analytics
Análisis de datos de ventas usando pandas y detección de anomalías
"""

import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Venta, Alerta
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Servicio para análisis de datos y generación de métricas"""
    
    @staticmethod
    def calculate_stats(db: Session) -> Dict[str, Any]:
        """
        Calcula estadísticas básicas de ventas
        
        Args:
            db: Sesión de base de datos
            
        Returns:
            Diccionario con métricas clave
        """
        ventas = db.query(Venta).all()
        
        if not ventas:
            logger.warning("No hay ventas para calcular estadísticas")
            return {
                "total_ventas": 0.0,
                "cantidad_transacciones": 0,
                "ticket_promedio": 0.0,
                "producto_mas_vendido": "N/A",
                "categoria_principal": "N/A"
            }
        
        # Convertir a DataFrame de pandas para análisis
        df = pd.DataFrame([{
            'monto_total': v.monto_total,
            'producto': v.nombre_producto,
            'categoria': v.categoria if v.categoria else "Sin categoría",
            'cantidad': v.cantidad
        } for v in ventas])
        
        # Calcular métricas
        total_ventas = float(df['monto_total'].sum())
        cantidad = len(df)
        ticket_promedio = total_ventas / cantidad if cantidad > 0 else 0.0
        
        # Producto más vendido (por cantidad de transacciones)
        producto_counts = df['producto'].value_counts()
        producto_top = str(producto_counts.index[0]) if len(producto_counts) > 0 else "N/A"
        
        # Categoría principal
        categoria_counts = df['categoria'].value_counts()
        categoria_top = str(categoria_counts.index[0]) if len(categoria_counts) > 0 else "N/A"
        
        logger.info(f"Estadísticas calculadas: {cantidad} transacciones, ${total_ventas:.2f} total")
        
        return {
            "total_ventas": round(total_ventas, 2),
            "cantidad_transacciones": cantidad,
            "ticket_promedio": round(ticket_promedio, 2),
            "producto_mas_vendido": producto_top,
            "categoria_principal": categoria_top
        }
    
    @staticmethod
    def detect_anomalies(db: Session) -> List[Alerta]:
        """
        Detecta anomalías en ventas y crea alertas automáticas
        Compara ventas recientes con promedio histórico
        
        Args:
            db: Sesión de base de datos
            
        Returns:
            Lista de alertas creadas
        """
        alertas_creadas = []
        
        # Obtener ventas de últimos 14 días
        hace_14_dias = datetime.now() - timedelta(days=14)
        ventas_recientes = db.query(Venta).filter(Venta.fecha >= hace_14_dias).all()
        
        if len(ventas_recientes) < 3:
            logger.info("No hay suficientes datos para detectar anomalías")
            return alertas_creadas
        
        # Convertir a DataFrame
        df = pd.DataFrame([{
            'fecha': v.fecha,
            'monto_total': v.monto_total
        } for v in ventas_recientes])
        
        # Agrupar por día
        df['dia'] = pd.to_datetime(df['fecha']).dt.date
        ventas_por_dia = df.groupby('dia')['monto_total'].sum()
        
        if len(ventas_por_dia) < 3:
            return alertas_creadas
        
        # Calcular promedio y última venta
        promedio = float(ventas_por_dia.mean())
        ultimo_dia = float(ventas_por_dia.iloc[-1])
        dias_analizados = len(ventas_por_dia)
        
        # ALERTA 1: Caída significativa de ventas (>30%)
        if ultimo_dia < promedio * 0.7:
            porcentaje_caida = ((promedio - ultimo_dia) / promedio) * 100
            alerta = Alerta(
                tipo="ventas",
                nivel="warning",
                mensaje=f"Ventas del último día (${ultimo_dia:.2f}) están {porcentaje_caida:.1f}% por debajo del promedio",
                detalles=f"Promedio últimos {dias_analizados} días: ${promedio:.2f}. Revisar posibles causas."
            )
            db.add(alerta)
            alertas_creadas.append(alerta)
            logger.warning(f"Alerta creada: Caída de ventas del {porcentaje_caida:.1f}%")
        
        # ALERTA 2: Ventas muy bajas (menos de $100 en el día)
        if ultimo_dia < 100 and promedio > 200:
            alerta = Alerta(
                tipo="ventas",
                nivel="critical",
                mensaje=f"Ventas críticas: solo ${ultimo_dia:.2f} en el último día",
                detalles="Ventas muy por debajo de lo normal. Requiere atención inmediata."
            )
            db.add(alerta)
            alertas_creadas.append(alerta)
            logger.critical(f"Alerta crítica: Ventas muy bajas ${ultimo_dia:.2f}")
        
        # ALERTA 3: Tendencia descendente (últimos 3 días)
        if len(ventas_por_dia) >= 3:
            ultimos_3 = ventas_por_dia.tail(3).values
            if all(ultimos_3[i] > ultimos_3[i+1] for i in range(len(ultimos_3)-1)):
                alerta = Alerta(
                    tipo="ventas",
                    nivel="warning",
                    mensaje="Tendencia descendente detectada: ventas cayendo 3 días consecutivos",
                    detalles=f"Día 1: ${ultimos_3[0]:.2f}, Día 2: ${ultimos_3[1]:.2f}, Día 3: ${ultimos_3[2]:.2f}"
                )
                db.add(alerta)
                alertas_creadas.append(alerta)
                logger.warning("Alerta creada: Tendencia descendente en ventas")
        
        # Commit de alertas
        if alertas_creadas:
            db.commit()
            logger.info(f"Se crearon {len(alertas_creadas)} alertas")
        
        return alertas_creadas
    
    @staticmethod
    def get_top_products(db: Session, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Obtiene los productos más vendidos
        
        Args:
            db: Sesión de base de datos
            limit: Cantidad de productos a retornar
            
        Returns:
            Lista de productos con sus métricas
        """
        ventas = db.query(Venta).all()
        
        if not ventas:
            return []
        
        df = pd.DataFrame([{
            'producto': v.nombre_producto,
            'producto_id': v.producto_id,
            'cantidad': v.cantidad,
            'monto': v.monto_total
        } for v in ventas])
        
        # Agrupar por producto
        productos_agg = df.groupby(['producto_id', 'producto']).agg({
            'cantidad': 'sum',
            'monto': 'sum'
        }).reset_index()
        
        # Ordenar por monto total
        top_productos = productos_agg.nlargest(limit, 'monto')
        
        resultado = []
        for _, row in top_productos.iterrows():
            resultado.append({
                'producto_id': row['producto_id'],
                'nombre': row['producto'],
                'cantidad_vendida': int(row['cantidad']),
                'monto_total': round(float(row['monto']), 2)
            })
        
        return resultado
