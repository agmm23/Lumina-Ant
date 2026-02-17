"""
Lumina_Ant - Servicio de Claude AI
Integración con la API de Anthropic para análisis inteligente de datos
"""

import anthropic
import json
from typing import List, Dict, Any
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)


class ClaudeService:
    """Servicio para interactuar con la API de Claude"""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.anthropic_api_key
        self.model = "claude-sonnet-4-20250514"

        # Modo demo si no hay API key configurada
        self.demo_mode = not self.api_key or self.api_key == ""

        if not self.demo_mode:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("Claude Service iniciado con API key configurada")
        else:
            self.client = None
            logger.warning("⚠️ Claude Service en MODO DEMO - usando respuestas simuladas (configura ANTHROPIC_API_KEY en .env para usar IA real)")
    
    async def analyze_sales(self, ventas_data: List[Dict]) -> Dict[str, Any]:
        """
        Analiza datos de ventas y genera insights accionables

        Args:
            ventas_data: Lista de diccionarios con información de ventas

        Returns:
            Diccionario con: resumen, insights, alertas, recomendaciones
        """
        # MODO DEMO: Retornar análisis simulado si no hay API key
        if self.demo_mode:
            return self._get_demo_analysis(ventas_data)

        # Limitar a 200 registros para no saturar el contexto
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

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # Limpiar markdown si existe
            response_text = self._clean_json_response(response_text)

            # Parsear JSON
            result = json.loads(response_text.strip())

            logger.info(f"Análisis de ventas completado exitosamente para {len(ventas_data)} registros")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Claude: {e}")
            logger.error(f"Respuesta recibida: {response_text}")
            return {
                "resumen": "No se pudo generar análisis automático",
                "insights": ["Error al procesar respuesta de IA"],
                "alertas": [],
                "recomendaciones": ["Revisar logs del sistema"]
            }

        except Exception as e:
            logger.error(f"Error llamando a Claude API: {e}")
            return {
                "resumen": "Error en servicio de IA",
                "insights": [],
                "alertas": [f"Error técnico: {str(e)}"],
                "recomendaciones": []
            }
    
    async def analyze_expenses(self, gastos_data: List[Dict]) -> Dict[str, Any]:
        """
        Analiza datos de gastos y genera insights accionables

        Args:
            gastos_data: Lista de diccionarios con información de gastos

        Returns:
            Diccionario con: resumen, insights, alertas, recomendaciones
        """
        # MODO DEMO: Retornar análisis simulado si no hay API key
        if self.demo_mode:
            return self._get_demo_analysis_expenses(gastos_data)

        # Limitar a 200 registros
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

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text.strip())

            logger.info(f"Análisis de gastos completado exitosamente para {len(gastos_data)} registros")
            return result

        except Exception as e:
            logger.error(f"Error analizando gastos: {e}")
            return {
                "resumen": "Error al analizar gastos",
                "insights": [],
                "alertas": [f"Error técnico: {str(e)}"],
                "recomendaciones": []
            }

    async def analyze_inventory(self, inventario_data: List[Dict]) -> Dict[str, Any]:
        """
        Analiza datos de inventario y genera insights accionables

        Args:
            inventario_data: Lista de diccionarios con información de inventario

        Returns:
            Diccionario con: resumen, insights, alertas, recomendaciones
        """
        # MODO DEMO: Retornar análisis simulado si no hay API key
        if self.demo_mode:
            return self._get_demo_analysis_inventory(inventario_data)

        # Limitar a 200 registros
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

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text.strip())

            logger.info(f"Análisis de inventario completado exitosamente para {len(inventario_data)} registros")
            return result

        except Exception as e:
            logger.error(f"Error analizando inventario: {e}")
            return {
                "resumen": "Error al analizar inventario",
                "insights": [],
                "alertas": [f"Error técnico: {str(e)}"],
                "recomendaciones": []
            }

    async def analyze_customers(self, clientes_data: List[Dict]) -> Dict[str, Any]:
        """
        Analiza datos de clientes y genera insights accionables

        Args:
            clientes_data: Lista de diccionarios con información de clientes

        Returns:
            Diccionario con: resumen, insights, alertas, recomendaciones
        """
        # MODO DEMO: Retornar análisis simulado si no hay API key
        if self.demo_mode:
            return self._get_demo_analysis_customers(clientes_data)

        # Limitar a 200 registros
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

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            response_text = self._clean_json_response(response_text)
            result = json.loads(response_text.strip())

            logger.info(f"Análisis de clientes completado exitosamente para {len(clientes_data)} registros")
            return result

        except Exception as e:
            logger.error(f"Error analizando clientes: {e}")
            return {
                "resumen": "Error al analizar clientes",
                "insights": [],
                "alertas": [f"Error técnico: {str(e)}"],
                "recomendaciones": []
            }

    async def explain_alert(self, alert_type: str, context: Dict) -> str:
        """
        Genera explicación detallada para una alerta detectada

        Args:
            alert_type: Tipo de alerta (ventas, gastos, inventario)
            context: Contexto adicional con datos relevantes

        Returns:
            Explicación en texto plano
        """
        # MODO DEMO: Retornar explicación simulada si no hay API key
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
            message = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            explanation = message.content[0].text.strip()
            logger.info(f"Explicación generada para alerta tipo: {alert_type}")
            return explanation

        except Exception as e:
            logger.error(f"Error generando explicación: {e}")
            return f"No se pudo generar explicación automática. Error: {str(e)}"
    
    def _get_demo_analysis(self, ventas_data: List[Dict]) -> Dict[str, Any]:
        """
        Genera análisis simulado para modo demo (sin API key)
        Calcula estadísticas reales pero usa insights pre-definidos
        """
        total_ventas = len(ventas_data)

        # Calcular algunas estadísticas básicas
        productos = {}
        categorias = {}
        total_monto = 0

        for venta in ventas_data:
            # Las claves vienen del router: 'producto', 'monto', 'categoria'
            producto = venta.get('producto', venta.get('nombre_producto', 'Desconocido'))
            categoria = venta.get('categoria', 'General')
            monto = venta.get('monto', venta.get('monto_total', 0))

            productos[producto] = productos.get(producto, 0) + 1
            categorias[categoria] = categorias.get(categoria, 0) + 1
            total_monto += float(monto) if monto else 0

        producto_top = max(productos.items(), key=lambda x: x[1])[0] if productos else "N/A"
        categoria_top = max(categorias.items(), key=lambda x: x[1])[0] if categorias else "N/A"

        logger.info(f"🎭 Generando análisis DEMO para {total_ventas} ventas")

        return {
            "resumen": f"📊 MODO DEMO: Análisis simulado de {total_ventas} transacciones. El negocio muestra actividad en {len(categorias)} categorías con {len(productos)} productos diferentes. Producto destacado: {producto_top}.",
            "insights": [
                f"✨ El producto '{producto_top}' lidera las ventas con {productos.get(producto_top, 0)} transacciones",
                f"📦 La categoría '{categoria_top}' concentra la mayor actividad comercial",
                f"💰 Se registraron {total_ventas} transacciones con un monto total de ${total_monto:,.2f}"
            ],
            "alertas": [
                "⚠️ Este es un análisis simulado - configura tu API key de Anthropic para obtener insights reales generados por IA"
            ],
            "recomendaciones": [
                f"🎯 Mantener stock adecuado de '{producto_top}' por su alta demanda",
                f"📈 Explorar oportunidades de cross-selling en la categoría '{categoria_top}'",
                "🔑 Configura ANTHROPIC_API_KEY en .env para análisis inteligentes personalizados"
            ]
        }

    def _get_demo_analysis_expenses(self, gastos_data: List[Dict]) -> Dict[str, Any]:
        """
        Genera análisis simulado de gastos para modo demo
        """
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

        logger.info(f"🎭 Generando análisis DEMO de gastos para {total_gastos} registros")

        return {
            "resumen": f"📊 MODO DEMO: Análisis simulado de {total_gastos} gastos con un total de ${total_monto:,.2f}. La categoría '{categoria_top}' representa el mayor gasto.",
            "insights": [
                f"💸 La categoría '{categoria_top}' concentra ${monto_top:,.2f} en gastos",
                f"📈 Se registraron {total_gastos} transacciones de gasto en {len(categorias)} categorías",
                f"💰 El gasto total acumulado es de ${total_monto:,.2f}"
            ],
            "alertas": [
                "⚠️ Este es un análisis simulado - configura tu API key de Anthropic para obtener insights reales generados por IA"
            ],
            "recomendaciones": [
                f"🎯 Revisar la categoría '{categoria_top}' para identificar oportunidades de optimización",
                "📊 Establecer presupuestos por categoría para mejor control de gastos",
                "🔑 Configura ANTHROPIC_API_KEY en .env para análisis inteligentes personalizados"
            ]
        }

    def _get_demo_analysis_inventory(self, inventario_data: List[Dict]) -> Dict[str, Any]:
        """
        Genera análisis simulado de inventario para modo demo
        """
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

        logger.info(f"🎭 Generando análisis DEMO de inventario para {total_items} items")

        return {
            "resumen": f"📦 MODO DEMO: Análisis simulado de {total_items} items de inventario valorizado en ${valor_total:,.2f}. Hay {items_bajo_stock} items con stock bajo.",
            "insights": [
                f"📊 La categoría '{categoria_top}' tiene la mayor cantidad de items registrados",
                f"💰 El valor total estimado del inventario es ${valor_total:,.2f}",
                f"⚠️ {items_bajo_stock} items necesitan reabastecimiento urgente"
            ],
            "alertas": [
                f"🚨 {items_bajo_stock} productos están por debajo del stock mínimo" if items_bajo_stock > 0 else "✅ No hay productos con stock crítico",
                "⚠️ Este es un análisis simulado - configura tu API key para insights reales"
            ],
            "recomendaciones": [
                "📋 Planificar reabastecimiento de productos con bajo stock",
                "💡 Implementar sistema de alertas automáticas para niveles mínimos",
                "🔑 Configura ANTHROPIC_API_KEY en .env para análisis inteligentes personalizados"
            ]
        }

    def _get_demo_analysis_customers(self, clientes_data: List[Dict]) -> Dict[str, Any]:
        """
        Genera análisis simulado de clientes para modo demo
        """
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

        logger.info(f"🎭 Generando análisis DEMO de clientes para {total_clientes} clientes")

        return {
            "resumen": f"👥 MODO DEMO: Análisis simulado de {total_clientes} clientes. {activos} están activos ({(activos/total_clientes*100):.1f}%). El tipo '{tipo_top}' es el más común.",
            "insights": [
                f"🎯 El segmento '{tipo_top}' representa la mayor parte de la base de clientes",
                f"✅ {activos} clientes están activos de un total de {total_clientes}",
                f"📊 La base de datos tiene {len(tipos)} tipos diferentes de clientes"
            ],
            "alertas": [
                f"⚠️ {total_clientes - activos} clientes están inactivos" if (total_clientes - activos) > 0 else "✅ Todos los clientes están activos",
                "⚠️ Este es un análisis simulado - configura tu API key para insights reales"
            ],
            "recomendaciones": [
                "🎯 Implementar campaña de reactivación para clientes inactivos",
                f"💡 Desarrollar estrategia específica para el segmento '{tipo_top}'",
                "🔑 Configura ANTHROPIC_API_KEY en .env para análisis inteligentes personalizados"
            ]
        }

    def _get_demo_explanation(self, alert_type: str, context: Dict) -> str:
        """
        Genera explicación simulada para alertas en modo demo
        """
        logger.info(f"🎭 Generando explicación DEMO para alerta tipo: {alert_type}")

        explanations = {
            "ventas_bajas": "📉 DEMO: Se detectó una disminución en las ventas. Esto podría deberse a factores estacionales, competencia o cambios en la demanda. Se recomienda revisar estrategias de marketing y precios.",
            "anomalia": "🔍 DEMO: Se identificó un patrón inusual en los datos. Es importante verificar si hay errores de registro o eventos especiales que expliquen esta variación.",
            "inventario": "📦 DEMO: Alerta de inventario. Se recomienda revisar niveles de stock y planificar reabastecimiento para productos de alta rotación.",
            "default": "⚠️ DEMO: Alerta del sistema. Este es un análisis simulado - configura tu API key de Anthropic para explicaciones detalladas generadas por IA."
        }

        return explanations.get(alert_type, explanations["default"])

    def _clean_json_response(self, text: str) -> str:
        """
        Limpia la respuesta para extraer JSON válido
        Remueve markdown code blocks si existen
        """
        # Remover ```json y ```
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]

        return text.strip()
