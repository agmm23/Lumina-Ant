"""
Lumina_Ant - Servicio de IA para análisis de datos
Soporta múltiples proveedores: Claude, OpenAI (ChatGPT), Gemini
Configurado desde .env con AI_PROVIDER
"""

import json
from typing import List, Dict, Any, Optional
from app.config import get_settings
from app.services.ai_provider import get_ai_provider, AIProvider
import logging

logger = logging.getLogger(__name__)


class AIService:
    """Servicio de IA multi-proveedor para análisis de datos de negocio."""

    def __init__(self):
        self.provider: Optional[AIProvider] = get_ai_provider()
        self.demo_mode = self.provider is None

        if not self.demo_mode:
            logger.info(f"AIService iniciado con proveedor: {self.provider.provider_name}")
        else:
            settings = get_settings()
            provider = settings.ai_provider.upper()
            key_map = {"CLAUDE": "ANTHROPIC_API_KEY", "OPENAI": "OPENAI_API_KEY", "GEMINI": "GOOGLE_API_KEY"}
            key_name = key_map.get(provider, "API_KEY")
            logger.warning(f"AIService en MODO DEMO — configura {key_name} en .env para usar IA real")

    async def analyze_sales(self, ventas_data: List[Dict]) -> Dict[str, Any]:
        if self.demo_mode:
            return self._get_demo_analysis(ventas_data)

        ventas_sample = ventas_data[:200] if len(ventas_data) > 200 else ventas_data

        prompt = f"""
Eres un analista de negocios experto especializado en PYMEs. Analiza estos datos de ventas:

{json.dumps(ventas_sample, indent=2, ensure_ascii=False)}

Total de registros analizados: {len(ventas_sample)} de {len(ventas_data)}

Proporciona un análisis completo:

1. RESUMEN EJECUTIVO (2-3 líneas sobre el estado general del negocio)

2. TOP 3 INSIGHTS ACCIONABLES (hallazgos importantes que el dueño debe conocer)

3. ALERTAS O RIESGOS (problemas detectados que requieren atención)

4. RECOMENDACIONES ESPECÍFICAS (acciones concretas para mejorar ventas)

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido (sin markdown, sin ```), con esta estructura exacta:
{{
  "resumen": "descripción breve del estado general",
  "insights": ["insight 1", "insight 2", "insight 3"],
  "alertas": ["alerta 1", "alerta 2"],
  "recomendaciones": ["recomendación 1", "recomendación 2", "recomendación 3"]
}}
"""
        return await self._call_and_parse(prompt, "ventas", len(ventas_data))

    async def analyze_expenses(self, gastos_data: List[Dict]) -> Dict[str, Any]:
        if self.demo_mode:
            return self._get_demo_analysis_expenses(gastos_data)

        gastos_sample = gastos_data[:200] if len(gastos_data) > 200 else gastos_data

        prompt = f"""
Eres un analista financiero experto para PYMEs. Analiza estos datos de gastos:

{json.dumps(gastos_sample, indent=2, ensure_ascii=False)}

Total de registros analizados: {len(gastos_sample)} de {len(gastos_data)}

Proporciona un análisis completo:

1. RESUMEN EJECUTIVO (2-3 líneas sobre el estado general de los gastos)

2. TOP 3 INSIGHTS ACCIONABLES (hallazgos importantes sobre el control de gastos)

3. ALERTAS O RIESGOS (gastos excesivos, categorías problemáticas)

4. RECOMENDACIONES ESPECÍFICAS (acciones para optimizar gastos)

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido (sin markdown, sin ```), con esta estructura exacta:
{{
  "resumen": "descripción breve del estado de gastos",
  "insights": ["insight 1", "insight 2", "insight 3"],
  "alertas": ["alerta 1", "alerta 2"],
  "recomendaciones": ["recomendación 1", "recomendación 2", "recomendación 3"]
}}
"""
        return await self._call_and_parse(prompt, "gastos", len(gastos_data))

    async def analyze_inventory(self, inventario_data: List[Dict]) -> Dict[str, Any]:
        if self.demo_mode:
            return self._get_demo_analysis_inventory(inventario_data)

        inventario_sample = inventario_data[:200] if len(inventario_data) > 200 else inventario_data

        prompt = f"""
Eres un experto en gestión de inventario para PYMEs. Analiza estos datos de inventario:

{json.dumps(inventario_sample, indent=2, ensure_ascii=False)}

Total de registros analizados: {len(inventario_sample)} de {len(inventario_data)}

Proporciona un análisis completo:

1. RESUMEN EJECUTIVO (2-3 líneas sobre el estado del inventario)

2. TOP 3 INSIGHTS ACCIONABLES (hallazgos sobre rotación, valorización, etc.)

3. ALERTAS O RIESGOS (productos con bajo stock, sobrestockados, obsoletos)

4. RECOMENDACIONES ESPECÍFICAS (acciones para optimizar inventario)

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido (sin markdown, sin ```), con esta estructura exacta:
{{
  "resumen": "descripción breve del estado del inventario",
  "insights": ["insight 1", "insight 2", "insight 3"],
  "alertas": ["alerta 1", "alerta 2"],
  "recomendaciones": ["recomendación 1", "recomendación 2", "recomendación 3"]
}}
"""
        return await self._call_and_parse(prompt, "inventario", len(inventario_data))

    async def analyze_customers(self, clientes_data: List[Dict]) -> Dict[str, Any]:
        if self.demo_mode:
            return self._get_demo_analysis_customers(clientes_data)

        clientes_sample = clientes_data[:200] if len(clientes_data) > 200 else clientes_data

        prompt = f"""
Eres un experto en gestión de relaciones con clientes (CRM) para PYMEs. Analiza estos datos de clientes:

{json.dumps(clientes_sample, indent=2, ensure_ascii=False)}

Total de registros analizados: {len(clientes_sample)} de {len(clientes_data)}

Proporciona un análisis completo:

1. RESUMEN EJECUTIVO (2-3 líneas sobre la base de clientes)

2. TOP 3 INSIGHTS ACCIONABLES (segmentación, oportunidades, patrones)

3. ALERTAS O RIESGOS (clientes inactivos, datos incompletos, concentración)

4. RECOMENDACIONES ESPECÍFICAS (acciones para mejorar relación con clientes)

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido (sin markdown, sin ```), con esta estructura exacta:
{{
  "resumen": "descripción breve de la base de clientes",
  "insights": ["insight 1", "insight 2", "insight 3"],
  "alertas": ["alerta 1", "alerta 2"],
  "recomendaciones": ["recomendación 1", "recomendación 2", "recomendación 3"]
}}
"""
        return await self._call_and_parse(prompt, "clientes", len(clientes_data))

    async def explain_alert(self, alert_type: str, context: Dict) -> str:
        if self.demo_mode:
            return self._get_demo_explanation(alert_type, context)

        prompt = f"""
Se ha detectado una alerta en el sistema de una PYME:

Tipo de alerta: {alert_type}
Contexto: {json.dumps(context, ensure_ascii=False, indent=2)}

Explica en 2-3 líneas:
1. Qué puede estar causando esta situación
2. Qué debería hacer el dueño del negocio al respecto

Responde en español, de forma clara y directa.
"""
        try:
            response = self.provider.single_prompt(prompt, max_tokens=300)
            logger.info(f"Explicación generada para alerta tipo: {alert_type} (via {self.provider.provider_name})")
            return response.strip()
        except Exception as e:
            logger.error(f"Error generando explicación via {self.provider.provider_name}: {e}")
            return f"No se pudo generar explicación automática. Error: {str(e)}"

    # ── Internal helpers ──────────────────────────────────────────

    async def _call_and_parse(self, prompt: str, category: str, total_records: int) -> Dict[str, Any]:
        """Llama al proveedor, parsea JSON, maneja errores."""
        try:
            response_text = self.provider.single_prompt(prompt, max_tokens=1500)
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text.strip())
            logger.info(f"Análisis de {category} completado via {self.provider.provider_name} ({total_records} registros)")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de {self.provider.provider_name}: {e}")
            return {
                "resumen": "No se pudo generar análisis automático",
                "insights": ["Error al procesar respuesta de IA"],
                "alertas": [],
                "recomendaciones": ["Revisar logs del sistema"],
            }
        except Exception as e:
            logger.error(f"Error llamando a {self.provider.provider_name}: {e}")
            return {
                "resumen": "Error en servicio de IA",
                "insights": [],
                "alertas": [f"Error técnico: {str(e)}"],
                "recomendaciones": [],
            }

    def _clean_json_response(self, text: str) -> str:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
        return text.strip()

    # ── Demo mode responses ───────────────────────────────────────

    def _get_demo_analysis(self, ventas_data: List[Dict]) -> Dict[str, Any]:
        total_ventas = len(ventas_data)
        productos = {}
        categorias = {}
        total_monto = 0

        for venta in ventas_data:
            producto = venta.get('producto', venta.get('nombre_producto', 'Desconocido'))
            categoria = venta.get('categoria', 'General')
            monto = venta.get('monto', venta.get('monto_total', 0))
            productos[producto] = productos.get(producto, 0) + 1
            categorias[categoria] = categorias.get(categoria, 0) + 1
            total_monto += float(monto) if monto else 0

        producto_top = max(productos.items(), key=lambda x: x[1])[0] if productos else "N/A"
        categoria_top = max(categorias.items(), key=lambda x: x[1])[0] if categorias else "N/A"

        return {
            "resumen": f"MODO DEMO: Análisis simulado de {total_ventas} transacciones. Producto destacado: {producto_top}.",
            "insights": [
                f"El producto '{producto_top}' lidera las ventas con {productos.get(producto_top, 0)} transacciones",
                f"La categoría '{categoria_top}' concentra la mayor actividad comercial",
                f"Se registraron {total_ventas} transacciones con un monto total de ${total_monto:,.2f}",
            ],
            "alertas": ["Este es un análisis simulado — configura tu API key para insights reales"],
            "recomendaciones": [
                f"Mantener stock adecuado de '{producto_top}' por su alta demanda",
                f"Explorar oportunidades de cross-selling en la categoría '{categoria_top}'",
                self._demo_key_hint(),
            ],
        }

    def _get_demo_analysis_expenses(self, gastos_data: List[Dict]) -> Dict[str, Any]:
        total_gastos = len(gastos_data)
        categorias = {}
        total_monto = 0

        for gasto in gastos_data:
            categoria = gasto.get('categoria', 'General')
            monto = gasto.get('monto', 0)
            categorias[categoria] = categorias.get(categoria, 0) + float(monto)
            total_monto += float(monto)

        categoria_top = max(categorias.items(), key=lambda x: x[1])[0] if categorias else "N/A"
        monto_top = categorias.get(categoria_top, 0)

        return {
            "resumen": f"MODO DEMO: Análisis simulado de {total_gastos} gastos con un total de ${total_monto:,.2f}.",
            "insights": [
                f"La categoría '{categoria_top}' concentra ${monto_top:,.2f} en gastos",
                f"Se registraron {total_gastos} transacciones en {len(categorias)} categorías",
                f"El gasto total acumulado es de ${total_monto:,.2f}",
            ],
            "alertas": ["Este es un análisis simulado — configura tu API key para insights reales"],
            "recomendaciones": [
                f"Revisar la categoría '{categoria_top}' para optimización",
                "Establecer presupuestos por categoría para mejor control",
                self._demo_key_hint(),
            ],
        }

    def _get_demo_analysis_inventory(self, inventario_data: List[Dict]) -> Dict[str, Any]:
        total_items = len(inventario_data)
        categorias = {}
        items_bajo_stock = 0
        valor_total = 0

        for item in inventario_data:
            categoria = item.get('categoria', 'General')
            cantidad = item.get('cantidad_actual', 0)
            cantidad_min = item.get('cantidad_minima', 0)
            precio = item.get('precio_venta', 0)
            categorias[categoria] = categorias.get(categoria, 0) + 1
            if cantidad_min and cantidad <= cantidad_min:
                items_bajo_stock += 1
            if precio:
                valor_total += float(cantidad) * float(precio)

        categoria_top = max(categorias.items(), key=lambda x: x[1])[0] if categorias else "N/A"

        return {
            "resumen": f"MODO DEMO: {total_items} items valorizado en ${valor_total:,.2f}. {items_bajo_stock} con stock bajo.",
            "insights": [
                f"La categoría '{categoria_top}' tiene la mayor cantidad de items",
                f"El valor total estimado del inventario es ${valor_total:,.2f}",
                f"{items_bajo_stock} items necesitan reabastecimiento",
            ],
            "alertas": [
                f"{items_bajo_stock} productos por debajo del stock mínimo" if items_bajo_stock > 0 else "No hay productos con stock crítico",
                "Este es un análisis simulado — configura tu API key para insights reales",
            ],
            "recomendaciones": [
                "Planificar reabastecimiento de productos con bajo stock",
                "Implementar alertas automáticas para niveles mínimos",
                self._demo_key_hint(),
            ],
        }

    def _get_demo_analysis_customers(self, clientes_data: List[Dict]) -> Dict[str, Any]:
        total_clientes = len(clientes_data)
        tipos = {}
        activos = 0

        for cliente in clientes_data:
            tipo = cliente.get('tipo_cliente', 'General')
            is_activo = cliente.get('activo', True)
            tipos[tipo] = tipos.get(tipo, 0) + 1
            if is_activo:
                activos += 1

        tipo_top = max(tipos.items(), key=lambda x: x[1])[0] if tipos else "N/A"

        return {
            "resumen": f"MODO DEMO: {total_clientes} clientes. {activos} activos ({(activos/total_clientes*100):.1f}%).",
            "insights": [
                f"El segmento '{tipo_top}' es el más representado",
                f"{activos} clientes activos de {total_clientes}",
                f"La base tiene {len(tipos)} tipos de clientes",
            ],
            "alertas": [
                f"{total_clientes - activos} clientes inactivos" if (total_clientes - activos) > 0 else "Todos los clientes están activos",
                "Este es un análisis simulado — configura tu API key para insights reales",
            ],
            "recomendaciones": [
                "Implementar campaña de reactivación para clientes inactivos",
                f"Desarrollar estrategia para el segmento '{tipo_top}'",
                self._demo_key_hint(),
            ],
        }

    def _get_demo_explanation(self, alert_type: str, context: Dict) -> str:
        explanations = {
            "ventas_bajas": "DEMO: Se detectó una disminución en las ventas. Podría deberse a factores estacionales o competencia.",
            "anomalia": "DEMO: Patrón inusual detectado. Verificar si hay errores de registro o eventos especiales.",
            "inventario": "DEMO: Alerta de inventario. Revisar niveles de stock y planificar reabastecimiento.",
            "default": "DEMO: Alerta del sistema. " + self._demo_key_hint(),
        }
        return explanations.get(alert_type, explanations["default"])

    def _demo_key_hint(self) -> str:
        settings = get_settings()
        provider = settings.ai_provider.upper()
        key_map = {"CLAUDE": "ANTHROPIC_API_KEY", "OPENAI": "OPENAI_API_KEY", "GEMINI": "GOOGLE_API_KEY"}
        key_name = key_map.get(provider, "API_KEY")
        return f"Configura {key_name} en .env para análisis con IA ({provider})"
