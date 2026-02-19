"""
Lumina_Ant - Servicio de Analytics
Análisis de datos de ventas usando pandas y detección de anomalías
"""

import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Venta, Gasto, Inventario, Alerta
from datetime import datetime, timedelta, date
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
    def _already_alerted(db: Session, tipo: str, nivel: str) -> bool:
        """Revisa si ya existe una alerta no leída del mismo tipo+nivel creada hoy."""
        hoy = datetime.combine(date.today(), datetime.min.time())
        return db.query(Alerta).filter(
            Alerta.tipo == tipo,
            Alerta.nivel == nivel,
            Alerta.leida == False,
            Alerta.fecha_creacion >= hoy,
        ).first() is not None

    @staticmethod
    def _add_alert(db: Session, alertas: list, tipo: str, nivel: str, mensaje: str, detalles: str):
        if AnalyticsService._already_alerted(db, tipo, nivel):
            return
        a = Alerta(tipo=tipo, nivel=nivel, mensaje=mensaje, detalles=detalles)
        db.add(a)
        alertas.append(a)
        logger.info(f"Alerta [{nivel}] {tipo}: {mensaje}")

    @staticmethod
    def detect_anomalies(db: Session) -> List[Alerta]:
        """
        Detecta anomalías en ventas, gastos e inventario.
        No crea duplicados: si ya existe una alerta no leída del mismo
        tipo+nivel creada hoy, la omite.
        """
        alertas_creadas = []

        # ── Ventas ────────────────────────────────────────────────
        hace_14_dias = datetime.now() - timedelta(days=14)
        ventas_recientes = db.query(Venta).filter(Venta.fecha >= hace_14_dias).all()

        if len(ventas_recientes) >= 3:
            df = pd.DataFrame([{
                'fecha': v.fecha, 'monto_total': v.monto_total
            } for v in ventas_recientes])
            df['dia'] = pd.to_datetime(df['fecha']).dt.date
            vpd = df.groupby('dia')['monto_total'].sum()

            if len(vpd) >= 3:
                promedio = float(vpd.mean())
                ultimo = float(vpd.iloc[-1])
                dias = len(vpd)

                # Caída >30%
                if ultimo < promedio * 0.7:
                    pct = ((promedio - ultimo) / promedio) * 100
                    AnalyticsService._add_alert(
                        db, alertas_creadas, "ventas", "warning",
                        f"Ventas del último día (${ultimo:,.0f}) están {pct:.0f}% por debajo del promedio",
                        f"Promedio últimos {dias} días: ${promedio:,.0f}.",
                    )

                # Ventas críticas
                if ultimo < 100 and promedio > 200:
                    AnalyticsService._add_alert(
                        db, alertas_creadas, "ventas", "critical",
                        f"Ventas críticas: solo ${ultimo:,.0f} en el último día",
                        "Ventas muy por debajo de lo normal. Requiere atención inmediata.",
                    )

                # Tendencia descendente 3 días
                u3 = vpd.tail(3).values
                if all(u3[i] > u3[i + 1] for i in range(len(u3) - 1)):
                    AnalyticsService._add_alert(
                        db, alertas_creadas, "ventas", "warning",
                        "Tendencia descendente: ventas cayendo 3 días consecutivos",
                        f"Día 1: ${u3[0]:,.0f}, Día 2: ${u3[1]:,.0f}, Día 3: ${u3[2]:,.0f}",
                    )

        # ── Gastos ────────────────────────────────────────────────
        gastos_recientes = db.query(Gasto).filter(Gasto.fecha >= hace_14_dias).all()

        if len(gastos_recientes) >= 3:
            dfg = pd.DataFrame([{
                'fecha': g.fecha, 'monto': g.monto
            } for g in gastos_recientes])
            dfg['dia'] = pd.to_datetime(dfg['fecha']).dt.date
            gpd = dfg.groupby('dia')['monto'].sum()

            if len(gpd) >= 3:
                prom_g = float(gpd.mean())
                ultimo_g = float(gpd.iloc[-1])

                # Pico de gastos >50% sobre promedio
                if ultimo_g > prom_g * 1.5:
                    pct = ((ultimo_g - prom_g) / prom_g) * 100
                    AnalyticsService._add_alert(
                        db, alertas_creadas, "gastos", "warning",
                        f"Gastos del último día (${ultimo_g:,.0f}) están {pct:.0f}% por encima del promedio",
                        f"Promedio últimos {len(gpd)} días: ${prom_g:,.0f}.",
                    )

                # Gastos excesivos (>2x promedio)
                if ultimo_g > prom_g * 2:
                    AnalyticsService._add_alert(
                        db, alertas_creadas, "gastos", "critical",
                        f"Gastos excesivos: ${ultimo_g:,.0f} en el último día (más del doble del promedio)",
                        "Revisar gastos inusuales de forma inmediata.",
                    )

                # Tendencia ascendente 3 días
                u3g = gpd.tail(3).values
                if all(u3g[i] < u3g[i + 1] for i in range(len(u3g) - 1)):
                    AnalyticsService._add_alert(
                        db, alertas_creadas, "gastos", "warning",
                        "Tendencia ascendente: gastos subiendo 3 días consecutivos",
                        f"Día 1: ${u3g[0]:,.0f}, Día 2: ${u3g[1]:,.0f}, Día 3: ${u3g[2]:,.0f}",
                    )

        # ── Inventario ────────────────────────────────────────────
        from sqlalchemy import func as sqlfunc

        bajos = db.query(Inventario).filter(
            Inventario.cantidad_minima.isnot(None),
            Inventario.cantidad_actual <= Inventario.cantidad_minima,
        ).all()

        if bajos:
            nombres = ", ".join(p.nombre_producto for p in bajos[:5])
            extra = f" y {len(bajos) - 5} más" if len(bajos) > 5 else ""
            nivel = "critical" if len(bajos) >= 5 else "warning"
            AnalyticsService._add_alert(
                db, alertas_creadas, "inventario", nivel,
                f"{len(bajos)} producto(s) con stock bajo o agotado",
                f"Productos: {nombres}{extra}.",
            )

        sin_stock = db.query(Inventario).filter(Inventario.cantidad_actual == 0).count()
        if sin_stock > 0:
            AnalyticsService._add_alert(
                db, alertas_creadas, "inventario", "critical",
                f"{sin_stock} producto(s) sin stock (cantidad = 0)",
                "Revisar reabastecimiento urgente.",
            )

        # ── Commit ────────────────────────────────────────────────
        if alertas_creadas:
            db.commit()
            logger.info(f"Detección automática: {len(alertas_creadas)} alerta(s) creada(s)")

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
