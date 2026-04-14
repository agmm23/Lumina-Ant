"""
Lumina_Ant - Servicio de Analytics
Análisis de datos de ventas usando pandas y detección de anomalías
"""

import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import Venta, Gasto, Inventario, Alerta, AlertConfig
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Servicio para análisis de datos y generación de métricas"""

    @staticmethod
    def calculate_stats(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Calcula estadísticas básicas de ventas del usuario.
        """
        ventas = db.query(Venta).filter(Venta.user_id == user_id).all()

        if not ventas:
            logger.warning(f"No hay ventas para user_id={user_id}")
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

        logger.info(f"Estadísticas calculadas user={user_id}: {cantidad} transacciones, ${total_ventas:.2f} total")

        return {
            "total_ventas": round(total_ventas, 2),
            "cantidad_transacciones": cantidad,
            "ticket_promedio": round(ticket_promedio, 2),
            "producto_mas_vendido": producto_top,
            "categoria_principal": categoria_top
        }

    @staticmethod
    def _already_alerted(db: Session, user_id: int, rule_id: str) -> bool:
        """Revisa si ya existe una alerta no leída de la misma regla creada hoy para este usuario."""
        hoy = datetime.combine(date.today(), datetime.min.time())
        return db.query(Alerta).filter(
            Alerta.user_id == user_id,
            Alerta.rule_id == rule_id,
            Alerta.leida == False,
            Alerta.fecha_creacion >= hoy,
        ).first() is not None

    @staticmethod
    def _add_alert(db: Session, user_id: int, alertas: list, rule_id: str, tipo: str, nivel: str, mensaje: str, detalles: str):
        if AnalyticsService._already_alerted(db, user_id, rule_id):
            return
        a = Alerta(user_id=user_id, tipo=tipo, nivel=nivel, rule_id=rule_id, mensaje=mensaje, detalles=detalles)
        db.add(a)
        alertas.append(a)
        logger.info(f"Alerta user={user_id} [{nivel}] {tipo}: {mensaje}")

    @staticmethod
    def _load_rule_params(db: Session, user_id: int) -> Dict[str, Dict[str, Any]]:
        """Carga params de cada regla del usuario, mergeando defaults con valores guardados."""
        from app.routers.analytics import RULE_META
        import json

        rule_params = {}
        configs = {
            c.rule_id: c
            for c in db.query(AlertConfig).filter(AlertConfig.user_id == user_id).all()
        }
        for rule_id, meta in RULE_META.items():
            defaults = {p["key"]: p["default"] for p in meta.get("params_def", [])}
            saved = json.loads(configs[rule_id].params) if rule_id in configs and configs[rule_id].params else {}
            defaults.update(saved)
            rule_params[rule_id] = defaults
        return rule_params

    @staticmethod
    def detect_anomalies(db: Session, user_id: int) -> List[Alerta]:
        """
        Detecta anomalías en ventas, gastos e inventario del usuario.
        No crea duplicados: si ya existe una alerta no leída del mismo
        tipo+nivel creada hoy, la omite.
        Usa parámetros configurables desde AlertConfig por usuario.
        """
        alertas_creadas = []

        # Cargar reglas habilitadas del usuario
        enabled_rules = {
            c.rule_id for c in db.query(AlertConfig).filter(
                AlertConfig.user_id == user_id,
                AlertConfig.enabled == True,
            ).all()
        }

        # Cargar parámetros configurables del usuario
        rp = AnalyticsService._load_rule_params(db, user_id)

        # ── Ventas ────────────────────────────────────────────────
        periodo_ventas = max(
            rp.get("ventas_caida", {}).get("periodo", 14),
            rp.get("ventas_tendencia", {}).get("dias", 3) + 1,
        )
        hace_n_dias = datetime.now() - timedelta(days=periodo_ventas)
        ventas_recientes = db.query(Venta).filter(
            Venta.user_id == user_id,
            Venta.fecha >= hace_n_dias,
        ).all()

        if len(ventas_recientes) >= 3:
            df = pd.DataFrame([{
                'fecha': v.fecha, 'monto_total': v.monto_total
            } for v in ventas_recientes])
            df['dia'] = pd.to_datetime(df['fecha']).dt.date
            vpd = df.groupby('dia')['monto_total'].sum()

            if len(vpd) >= 3:
                promedio = float(vpd.mean())
                ultimo = float(vpd.iloc[-1])
                dias_datos = len(vpd)

                # Caída de ventas
                umbral_caida = rp.get("ventas_caida", {}).get("umbral", 30)
                if "ventas_caida" in enabled_rules and ultimo < promedio * (1 - umbral_caida / 100):
                    pct = ((promedio - ultimo) / promedio) * 100
                    AnalyticsService._add_alert(
                        db, user_id, alertas_creadas, "ventas_caida", "ventas", "warning",
                        f"Ventas del último día (${ultimo:,.0f}) están {pct:.0f}% por debajo del promedio",
                        f"Promedio últimos {dias_datos} días: ${promedio:,.0f}.",
                    )

                # Ventas críticas
                minimo = rp.get("ventas_criticas", {}).get("minimo", 100)
                promedio_min = rp.get("ventas_criticas", {}).get("promedio_min", 200)
                if "ventas_criticas" in enabled_rules and ultimo < minimo and promedio > promedio_min:
                    AnalyticsService._add_alert(
                        db, user_id, alertas_creadas, "ventas_criticas", "ventas", "critical",
                        f"Ventas críticas: solo ${ultimo:,.0f} en el último día",
                        "Ventas muy por debajo de lo normal. Requiere atención inmediata.",
                    )

                # Tendencia descendente N días
                dias_tend = rp.get("ventas_tendencia", {}).get("dias", 3)
                uN = vpd.tail(dias_tend).values
                if "ventas_tendencia" in enabled_rules and len(uN) >= dias_tend and all(uN[i] > uN[i + 1] for i in range(len(uN) - 1)):
                    detalle = ", ".join(f"Día {i+1}: ${uN[i]:,.0f}" for i in range(len(uN)))
                    AnalyticsService._add_alert(
                        db, user_id, alertas_creadas, "ventas_tendencia", "ventas", "warning",
                        f"Tendencia descendente: ventas cayendo {dias_tend} días consecutivos",
                        detalle,
                    )

        # ── Gastos ────────────────────────────────────────────────
        periodo_gastos = max(
            rp.get("gastos_pico", {}).get("periodo", 14),
            rp.get("gastos_tendencia", {}).get("dias", 3) + 1,
        )
        hace_n_dias_g = datetime.now() - timedelta(days=periodo_gastos)
        gastos_recientes = db.query(Gasto).filter(
            Gasto.user_id == user_id,
            Gasto.fecha >= hace_n_dias_g,
        ).all()

        if len(gastos_recientes) >= 3:
            dfg = pd.DataFrame([{
                'fecha': g.fecha, 'monto': g.monto
            } for g in gastos_recientes])
            dfg['dia'] = pd.to_datetime(dfg['fecha']).dt.date
            gpd = dfg.groupby('dia')['monto'].sum()

            if len(gpd) >= 3:
                prom_g = float(gpd.mean())
                ultimo_g = float(gpd.iloc[-1])

                # Pico de gastos
                umbral_pico = rp.get("gastos_pico", {}).get("umbral", 50)
                if "gastos_pico" in enabled_rules and ultimo_g > prom_g * (1 + umbral_pico / 100):
                    pct = ((ultimo_g - prom_g) / prom_g) * 100
                    AnalyticsService._add_alert(
                        db, user_id, alertas_creadas, "gastos_pico", "gastos", "warning",
                        f"Gastos del último día (${ultimo_g:,.0f}) están {pct:.0f}% por encima del promedio",
                        f"Promedio últimos {len(gpd)} días: ${prom_g:,.0f}.",
                    )

                # Gastos excesivos
                multiplicador = rp.get("gastos_excesivos", {}).get("multiplicador", 2)
                if "gastos_excesivos" in enabled_rules and ultimo_g > prom_g * multiplicador:
                    AnalyticsService._add_alert(
                        db, user_id, alertas_creadas, "gastos_excesivos", "gastos", "critical",
                        f"Gastos excesivos: ${ultimo_g:,.0f} en el último día ({multiplicador}x el promedio)",
                        "Revisar gastos inusuales de forma inmediata.",
                    )

                # Tendencia ascendente N días
                dias_tend_g = rp.get("gastos_tendencia", {}).get("dias", 3)
                uNg = gpd.tail(dias_tend_g).values
                if "gastos_tendencia" in enabled_rules and len(uNg) >= dias_tend_g and all(uNg[i] < uNg[i + 1] for i in range(len(uNg) - 1)):
                    detalle = ", ".join(f"Día {i+1}: ${uNg[i]:,.0f}" for i in range(len(uNg)))
                    AnalyticsService._add_alert(
                        db, user_id, alertas_creadas, "gastos_tendencia", "gastos", "warning",
                        f"Tendencia ascendente: gastos subiendo {dias_tend_g} días consecutivos",
                        detalle,
                    )

        # ── Inventario ────────────────────────────────────────────
        if "inventario_bajo" in enabled_rules:
            bajos = db.query(Inventario).filter(
                Inventario.user_id == user_id,
                Inventario.cantidad_minima.isnot(None),
                Inventario.cantidad_actual <= Inventario.cantidad_minima,
            ).all()

            if bajos:
                nombres = ", ".join(p.nombre_producto for p in bajos[:5])
                extra = f" y {len(bajos) - 5} más" if len(bajos) > 5 else ""
                nivel = "critical" if len(bajos) >= 5 else "warning"
                AnalyticsService._add_alert(
                    db, user_id, alertas_creadas, "inventario_bajo", "inventario", nivel,
                    f"{len(bajos)} producto(s) con stock bajo o agotado",
                    f"Productos: {nombres}{extra}.",
                )

        if "inventario_sin_stock" in enabled_rules:
            sin_stock = db.query(Inventario).filter(
                Inventario.user_id == user_id,
                Inventario.cantidad_actual == 0,
            ).count()
            if sin_stock > 0:
                AnalyticsService._add_alert(
                    db, user_id, alertas_creadas, "inventario_sin_stock", "inventario", "critical",
                    f"{sin_stock} producto(s) sin stock (cantidad = 0)",
                    "Revisar reabastecimiento urgente.",
                )

        # ── Commit ────────────────────────────────────────────────
        if alertas_creadas:
            db.commit()
            logger.info(f"Detección automática user={user_id}: {len(alertas_creadas)} alerta(s) creada(s)")

        return alertas_creadas

    @staticmethod
    def get_top_products(db: Session, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Obtiene los productos más vendidos del usuario.
        """
        ventas = db.query(Venta).filter(Venta.user_id == user_id).all()

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
