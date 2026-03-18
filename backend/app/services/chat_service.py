"""
Lumina_Ant - Servicio de Chat/Copilot IA
Pipeline: Clasificar intent → Consultar datos → Calcular con pandas → Interpretar con IA
Soporta múltiples proveedores: Claude, OpenAI (ChatGPT), Gemini
"""

import json
import os
import time
import pandas as pd
from typing import AsyncIterator, List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.models import Venta, Gasto, Inventario, Cliente
from app.services.ai_provider import get_ai_provider, AIProvider
from datetime import datetime, timedelta
import logging
import unicodedata
import re

logger = logging.getLogger(__name__)

# ── Analytics log (JSONL diario) ─────────────────────────────────
_LOG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
os.makedirs(_LOG_DIR, exist_ok=True)


def _write_analytics(entry: Dict) -> None:
    """Añade una línea JSONL al archivo de analytics del día."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(_LOG_DIR, f"chat_{today}.jsonl")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning(f"No se pudo escribir analytics: {exc}")


# ── Detección de preguntas no resolubles ──────────────────────────
_UNRESOLVABLE_PATTERNS: List[Tuple[str, str]] = [
    (r"no (tengo|hay|dispongo de|cuento con).{0,40}(datos|informaci[oó]n|suficiente|detalle)", "sin datos suficientes"),
    (r"no (puedo|podr[ií]a).{0,40}(responder|determinar|calcular|saber|indicar|precisar)", "no puede responder"),
    (r"(informaci[oó]n|datos).{0,25}(insuficiente|limitad|no disponible)", "datos insuficientes"),
    (r"necesitar[ií]a?.{0,30}(m[aá]s|mayor).{0,20}(detalle|informaci[oó]n|datos)", "necesita más datos"),
    (r"para (poder )?responder.{0,30}(necesito|requiero|falta)", "faltan datos para responder"),
    (r"no (se|est[aá]) (cargad|registrad|encontr)", "datos no cargados"),
    (r"no (tengo|dispongo).{0,20}acceso", "sin acceso a los datos"),
    (r"(pregunta|consulta).{0,30}(fuera de|no (est[aá]|cae) (en|dentro))", "fuera de alcance"),
]


def _detect_unresolvable(text: str) -> Tuple[bool, Optional[str]]:
    """
    Analiza el texto de respuesta de la IA para detectar si no pudo resolver la pregunta.
    Retorna (es_irresoluble, señal_detectada).
    """
    normalized = _normalize(text)
    for pattern, label in _UNRESOLVABLE_PATTERNS:
        if re.search(pattern, normalized):
            return True, label
    return False, None

# ── Intent classification ──────────────────────────────────────────

INTENT_MAP = {
    "ventas": {
        "keywords": [
            "venta", "ventas", "vendido", "vendieron", "facturado",
            "ingreso", "ingresos", "revenue", "mejor mes", "peor mes",
            "producto mas vendido", "mas vendido", "ticket promedio",
        ],
        "tables": ["ventas"],
    },
    "gastos": {
        "keywords": [
            "gasto", "gastos", "costo", "costos", "pagos", "egresos",
            "proveedor", "proveedores", "factura", "facturas",
        ],
        "tables": ["gastos"],
    },
    "inventario": {
        "keywords": [
            "inventario", "stock", "reabastecer", "agotado", "almacen",
            "bajo stock", "sin stock", "reposicion", "producto",
            "productos", "existencias",
        ],
        "tables": ["inventario"],
    },
    "clientes": {
        "keywords": [
            "cliente", "clientes", "comprador", "compradores",
            "activos", "inactivos", "tipo cliente", "crm",
        ],
        "tables": ["clientes"],
    },
    "general": {
        "keywords": [
            "negocio", "empresa", "resumen", "general", "todo",
            "panorama", "comparar", "como va", "como estamos",
        ],
        "tables": ["ventas", "gastos", "inventario", "clientes"],
    },
    # ── Intents cruzados (Fase 3) ──────────────────────────────────
    "rentabilidad": {
        "keywords": [
            "rentable", "rentabilidad", "margen", "ganancia", "ganancias",
            "perdida", "perdidas", "beneficio", "cuanto gano", "cuanto me queda",
            "me conviene", "utilidad", "utilidades", "flujo de caja",
            "cuanto queda", "sobra", "resultado",
        ],
        "tables": ["ventas", "gastos"],
    },
    "rotacion": {
        "keywords": [
            "sin movimiento", "no se vende", "no se mueve", "parado", "parados",
            "rotacion", "productos muertos", "obsoleto", "obsoletos",
            "no ha vendido", "sin ventas", "productos lentos",
        ],
        "tables": ["inventario", "ventas"],
    },
    "clientes_ventas": {
        "keywords": [
            "recurrente", "recurrentes", "fiel", "fieles", "repite", "repiten",
            "vuelve", "vuelven", "frecuencia de compra", "mejor cliente",
            "cliente top", "clientes top", "cuanto compra", "ticket por cliente",
        ],
        "tables": ["clientes", "ventas"],
    },
}

SUGGESTED_PROMPTS = [
    {"text": "¿Cuál fue mi mejor mes de ventas?", "icon": "📈", "category": "ventas"},
    {"text": "¿Qué productos debería reabastecer?", "icon": "📦", "category": "inventario"},
    {"text": "¿Cómo van mis gastos este mes?", "icon": "💸", "category": "gastos"},
    {"text": "Dame un resumen general del negocio", "icon": "🏢", "category": "general"},
    {"text": "¿Cuál es mi producto más vendido?", "icon": "⭐", "category": "ventas"},
    {"text": "¿Cuántos clientes activos tengo?", "icon": "👥", "category": "clientes"},
    {"text": "¿Cuál es mi margen de ganancia?", "icon": "💰", "category": "general"},
    {"text": "¿Qué categorías de gasto son las más altas?", "icon": "📊", "category": "gastos"},
]

FOLLOWUPS = {
    "ventas": [
        "¿Cuál es la tendencia de ventas del último mes?",
        "¿Qué productos debería promover más?",
        "¿Cómo se comparan las ventas con los gastos?",
    ],
    "gastos": [
        "¿Dónde puedo recortar gastos?",
        "¿Cuál es el gasto más grande del mes?",
        "¿Cómo se comparan los gastos con las ventas?",
    ],
    "inventario": [
        "¿Qué productos tienen mayor rotación?",
        "¿Cuál es el valor total del inventario?",
        "¿Hay productos sin movimiento?",
    ],
    "clientes": [
        "¿Cuántos clientes nuevos tengo este mes?",
        "¿Qué tipo de cliente es el más común?",
        "¿Hay clientes inactivos que debería contactar?",
    ],
    "general": [
        "¿Cuál fue mi mejor mes de ventas?",
        "¿Qué productos debería reabastecer?",
        "¿Cómo van mis gastos este mes?",
    ],
    "rentabilidad": [
        "¿Cuál es la categoría de gasto que más reduce mi margen?",
        "¿En qué mes tuve mejor margen de ganancia?",
        "¿Cómo puedo mejorar mi rentabilidad?",
    ],
    "rotacion": [
        "¿Qué productos tienen mayor rotación?",
        "¿Cuánto dinero tengo inmovilizado en productos sin movimiento?",
        "¿Qué debería liquidar o descontinuar?",
    ],
    "clientes_ventas": [
        "¿Cuánto gasta en promedio cada tipo de cliente?",
        "¿Qué productos prefieren mis mejores clientes?",
        "¿Hay clientes inactivos que debería reactivar?",
    ],
}

# ── Helpers de entidades ───────────────────────────────────────────

MONTH_NAMES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
}


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_date_filter(message: str) -> Optional[tuple]:
    """
    Detecta mes/año en el mensaje.
    Retorna (year, month) o None.
    """
    normalized = _normalize(message)
    for name, month_num in MONTH_NAMES.items():
        if name in normalized:
            m = re.search(r'\b(20\d{2})\b', message)
            year = int(m.group(1)) if m else datetime.now().year
            return (year, month_num)
    if 'este mes' in normalized or 'mes actual' in normalized:
        now = datetime.now()
        return (now.year, now.month)
    return None


def _find_entity(message: str, candidates) -> Optional[str]:
    """
    Busca si algún nombre de la lista aparece en el mensaje.
    Requiere mínimo 3 caracteres para evitar falsos positivos.
    """
    norm_msg = _normalize(message)
    for candidate in candidates:
        nc = _normalize(str(candidate))
        if len(nc) >= 3 and nc in norm_msg:
            return candidate
    return None


class ChatService:
    """Servicio de Chat/Copilot con pipeline Retrieve-Compute-Interpret."""

    def __init__(self):
        self.provider: Optional[AIProvider] = get_ai_provider()
        self.demo_mode = self.provider is None

        if not self.demo_mode:
            logger.info(f"ChatService iniciado con proveedor: {self.provider.provider_name}")
        else:
            logger.warning("ChatService en MODO DEMO")

    # ── Public API ──────────────────────────────────────────────────

    async def chat(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        db: Session,
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje del usuario y retorna respuesta del copilot.
        Pipeline: classify → query → compute → interpret.
        """
        t0 = time.monotonic()
        intents = self._classify_intent(user_message)
        logger.info(f"Chat intents: {intents} for message: {user_message[:80]}")

        context: Dict[str, Any] = {}
        tables_needed: set = set()
        for intent in intents:
            for table in INTENT_MAP.get(intent, {}).get("tables", []):
                tables_needed.add(table)

        for table in tables_needed:
            ctx = self._get_table_context(table, db, user_message)
            if ctx:
                context[table] = ctx

        if self.demo_mode:
            result = self._demo_response(user_message, intents, context)
            self._log_interaction(
                mode="chat", message=user_message, intents=intents, context=context,
                response_text=result["content"], duration_ms=int((time.monotonic() - t0) * 1000),
                demo_mode=True,
            )
            return result

        system_prompt = self._build_system_prompt(context)

        messages = []
        for msg in history[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        try:
            content = self.provider.chat_completion(
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=1500,
            )
            usage = self.provider.get_last_usage()
            logger.info(f"Chat response via {self.provider.provider_name} ({len(content)} chars) tokens={usage.get('total_tokens', '?')}")
            self._log_interaction(
                mode="chat", message=user_message, intents=intents, context=context,
                response_text=content, duration_ms=int((time.monotonic() - t0) * 1000),
                usage=usage,
            )
            return {
                "role": "assistant",
                "content": content,
                "intents": intents,
                "data_sources": list(context.keys()),
            }
        except Exception as e:
            logger.error(f"Error en {self.provider.provider_name} API: {e}")
            self._log_interaction(
                mode="chat", message=user_message, intents=intents, context=context,
                response_text="", duration_ms=int((time.monotonic() - t0) * 1000),
                error=str(e),
            )
            return {
                "role": "assistant",
                "content": f"Lo siento, hubo un error al procesar tu pregunta. Detalle: {str(e)}",
                "intents": intents,
                "data_sources": list(context.keys()),
            }

    # ── Intent classification ──────────────────────────────────────

    def _classify_intent(self, message: str) -> List[str]:
        """Classify user intent by keyword scoring. Returns sorted list of matching intents."""
        normalized = _normalize(message)
        scores: Dict[str, int] = {}

        for intent, cfg in INTENT_MAP.items():
            score = 0
            for kw in cfg["keywords"]:
                kw_norm = _normalize(kw)
                if kw_norm in normalized:
                    score += len(kw_norm.split())
            if score > 0:
                scores[intent] = score

        if not scores:
            return ["general"]

        sorted_intents = sorted(scores, key=scores.get, reverse=True)
        return sorted_intents

    # ── Data context retrieval ─────────────────────────────────────

    def _get_table_context(self, table: str, db: Session, message: str = "") -> Optional[Dict[str, Any]]:
        """Dispatch to the right context builder, passing the user message for adaptive context."""
        builders = {
            "ventas": self._get_ventas_context,
            "gastos": self._get_gastos_context,
            "inventario": self._get_inventario_context,
            "clientes": self._get_clientes_context,
        }
        builder = builders.get(table)
        if builder:
            return builder(db, message)
        return None

    def _get_ventas_context(self, db: Session, message: str = "") -> Dict[str, Any]:
        ventas = db.query(Venta).all()
        if not ventas:
            return {"sin_datos": True, "mensaje": "No hay datos de ventas cargados."}

        df = pd.DataFrame([{
            "fecha": v.fecha,
            "producto": v.nombre_producto,
            "cantidad": v.cantidad,
            "monto": v.monto_total,
            "categoria": v.categoria or "Sin categoría",
        } for v in ventas])

        df["fecha"] = pd.to_datetime(df["fecha"])
        total = float(df["monto"].sum())
        count = len(df)
        ticket_promedio = total / count if count else 0

        # Opción 1: Top 20 productos (era 5)
        top_prod = df.groupby("producto")["monto"].sum().sort_values(ascending=False).head(20)
        top_productos = [{"nombre": n, "monto": round(float(v), 2)} for n, v in top_prod.items()]

        # Opción 1: Top 10 categorías (era 5)
        top_cat = df.groupby("categoria")["monto"].sum().sort_values(ascending=False).head(10)
        top_categorias = [{"nombre": n, "monto": round(float(v), 2)} for n, v in top_cat.items()]

        # Opción 1: Tendencia mensual 12 meses (era 6)
        df["mes"] = df["fecha"].dt.to_period("M")
        mensual = df.groupby("mes")["monto"].sum().sort_index()
        tendencia_mensual = [
            {"mes": str(p), "monto": round(float(v), 2)} for p, v in mensual.tail(12).items()
        ]

        mejor_mes = mensual.idxmax() if len(mensual) else None
        peor_mes = mensual.idxmin() if len(mensual) else None

        # Opción 1: Ventas semanales últimas 4 semanas (siempre)
        hace_4s = pd.Timestamp.now() - pd.Timedelta(weeks=4)
        df_rec = df[df["fecha"] >= hace_4s].copy()
        if not df_rec.empty:
            df_rec["semana"] = df_rec["fecha"].dt.to_period("W")
            semanal = df_rec.groupby("semana")["monto"].sum().sort_index()
            semanas_recientes = [{"semana": str(p), "monto": round(float(v), 2)} for p, v in semanal.items()]
        else:
            semanas_recientes = []

        result = {
            "total_ventas": round(total, 2),
            "num_transacciones": count,
            "ticket_promedio": round(ticket_promedio, 2),
            "top_productos": top_productos,
            "top_categorias": top_categorias,
            "tendencia_mensual": tendencia_mensual,
            "semanas_recientes": semanas_recientes,
            "mejor_mes": {"mes": str(mejor_mes), "monto": round(float(mensual[mejor_mes]), 2)} if mejor_mes is not None else None,
            "peor_mes": {"mes": str(peor_mes), "monto": round(float(mensual[peor_mes]), 2)} if peor_mes is not None else None,
        }

        # Opción 2: drill-down adaptativo
        if message:
            # Producto específico mencionado
            matched = _find_entity(message, df["producto"].dropna().unique().tolist())
            if matched:
                prod_df = df[df["producto"] == matched].copy()
                prod_mensual = prod_df.groupby("mes")["monto"].sum().sort_index()
                result["drill_down_producto"] = {
                    "nombre": matched,
                    "total": round(float(prod_df["monto"].sum()), 2),
                    "cantidad_total": int(prod_df["cantidad"].sum()),
                    "transacciones": len(prod_df),
                    "ticket_promedio": round(float(prod_df["monto"].mean()), 2),
                    "tendencia_mensual": [
                        {"mes": str(p), "monto": round(float(v), 2)} for p, v in prod_mensual.items()
                    ],
                }

            # Mes/año específico mencionado
            date_f = _extract_date_filter(message)
            if date_f:
                year, month = date_f
                period_df = df[(df["fecha"].dt.year == year) & (df["fecha"].dt.month == month)].copy()
                if not period_df.empty:
                    period_df["semana"] = period_df["fecha"].dt.isocalendar().week
                    semanal_p = period_df.groupby("semana")["monto"].sum()
                    top_p = period_df.groupby("producto")["monto"].sum().sort_values(ascending=False).head(10)
                    result["drill_down_periodo"] = {
                        "periodo": f"{year}-{month:02d}",
                        "total": round(float(period_df["monto"].sum()), 2),
                        "transacciones": len(period_df),
                        "ticket_promedio": round(float(period_df["monto"].mean()), 2),
                        "top_productos": [{"nombre": k, "monto": round(float(v), 2)} for k, v in top_p.items()],
                        "por_semana": [{"semana": int(k), "monto": round(float(v), 2)} for k, v in semanal_p.items()],
                    }

        return result

    def _get_gastos_context(self, db: Session, message: str = "") -> Dict[str, Any]:
        gastos = db.query(Gasto).all()
        if not gastos:
            return {"sin_datos": True, "mensaje": "No hay datos de gastos cargados."}

        df = pd.DataFrame([{
            "fecha": g.fecha,
            "descripcion": g.descripcion,
            "categoria": g.categoria,
            "monto": g.monto,
            "proveedor": g.nombre_proveedor or "Sin proveedor",
        } for g in gastos])

        df["fecha"] = pd.to_datetime(df["fecha"])
        total = float(df["monto"].sum())
        count = len(df)

        top_cat = df.groupby("categoria")["monto"].sum().sort_values(ascending=False).head(5)
        top_categorias = [{"nombre": n, "monto": round(float(v), 2)} for n, v in top_cat.items()]

        # Opción 1: Tendencia 12 meses (era 6)
        df["mes"] = df["fecha"].dt.to_period("M")
        mensual = df.groupby("mes")["monto"].sum().sort_index()
        tendencia_mensual = [
            {"mes": str(p), "monto": round(float(v), 2)} for p, v in mensual.tail(12).items()
        ]

        idx_max = df["monto"].idxmax()
        gasto_max = {
            "descripcion": df.loc[idx_max, "descripcion"],
            "monto": round(float(df.loc[idx_max, "monto"]), 2),
            "categoria": df.loc[idx_max, "categoria"],
        }

        # Opción 1: Top 10 proveedores (nuevo)
        top_prov = df.groupby("proveedor")["monto"].sum().sort_values(ascending=False).head(10)
        top_proveedores = [{"nombre": n, "monto": round(float(v), 2)} for n, v in top_prov.items()]

        result = {
            "total_gastos": round(total, 2),
            "num_transacciones": count,
            "gasto_promedio": round(total / count, 2) if count else 0,
            "top_categorias": top_categorias,
            "top_proveedores": top_proveedores,
            "tendencia_mensual": tendencia_mensual,
            "gasto_mas_grande": gasto_max,
        }

        # Opción 2: drill-down adaptativo
        if message:
            # Proveedor específico mencionado
            matched_prov = _find_entity(message, df["proveedor"].dropna().unique().tolist())
            if matched_prov and matched_prov != "Sin proveedor":
                prov_df = df[df["proveedor"] == matched_prov]
                cats_prov = prov_df.groupby("categoria")["monto"].sum().sort_values(ascending=False).head(5)
                ultimo = prov_df.loc[prov_df["fecha"].idxmax()]
                result["drill_down_proveedor"] = {
                    "nombre": matched_prov,
                    "total": round(float(prov_df["monto"].sum()), 2),
                    "transacciones": len(prov_df),
                    "categorias": [{"nombre": k, "monto": round(float(v), 2)} for k, v in cats_prov.items()],
                    "ultimo_gasto": {
                        "descripcion": ultimo["descripcion"],
                        "monto": round(float(ultimo["monto"]), 2),
                        "fecha": str(ultimo["fecha"].date()),
                    },
                }

            # Mes/año específico mencionado
            date_f = _extract_date_filter(message)
            if date_f:
                year, month = date_f
                period_df = df[(df["fecha"].dt.year == year) & (df["fecha"].dt.month == month)]
                if not period_df.empty:
                    top_cat_p = period_df.groupby("categoria")["monto"].sum().sort_values(ascending=False).head(10)
                    top_prov_p = period_df.groupby("proveedor")["monto"].sum().sort_values(ascending=False).head(10)
                    result["drill_down_periodo"] = {
                        "periodo": f"{year}-{month:02d}",
                        "total": round(float(period_df["monto"].sum()), 2),
                        "transacciones": len(period_df),
                        "top_categorias": [{"nombre": k, "monto": round(float(v), 2)} for k, v in top_cat_p.items()],
                        "top_proveedores": [{"nombre": k, "monto": round(float(v), 2)} for k, v in top_prov_p.items()],
                    }

        return result

    def _get_inventario_context(self, db: Session, message: str = "") -> Dict[str, Any]:
        items = db.query(Inventario).all()
        if not items:
            return {"sin_datos": True, "mensaje": "No hay datos de inventario cargados."}

        total_items = len(items)
        bajo_stock = []
        sin_stock = []
        valor_total = 0.0

        for item in items:
            precio = item.precio_venta or 0
            valor_total += item.cantidad_actual * precio
            if item.cantidad_actual == 0:
                sin_stock.append(item.nombre_producto)
            elif item.cantidad_minima and item.cantidad_actual <= item.cantidad_minima:
                bajo_stock.append({
                    "nombre": item.nombre_producto,
                    "actual": item.cantidad_actual,
                    "minimo": item.cantidad_minima,
                })

        # Opción 1: Top 10 por valor (era 5), listas completas (era [:10])
        items_sorted = sorted(items, key=lambda x: x.cantidad_actual * (x.precio_venta or 0), reverse=True)
        top_valor = [
            {"nombre": i.nombre_producto, "cantidad": i.cantidad_actual, "valor": round(i.cantidad_actual * (i.precio_venta or 0), 2)}
            for i in items_sorted[:10]
        ]

        result = {
            "total_productos": total_items,
            "valor_total_inventario": round(valor_total, 2),
            "productos_bajo_stock": bajo_stock,       # lista completa (era [:10])
            "productos_sin_stock": sin_stock,          # lista completa (era [:10])
            "num_bajo_stock": len(bajo_stock),
            "num_sin_stock": len(sin_stock),
            "top_por_valor": top_valor,
        }

        # Opción 2: drill-down adaptativo
        if message:
            all_names = [i.nombre_producto for i in items]
            matched = _find_entity(message, all_names)
            if matched:
                item = next((i for i in items if i.nombre_producto == matched), None)
                if item:
                    if item.cantidad_actual == 0:
                        estado = "sin_stock"
                    elif item.cantidad_minima and item.cantidad_actual <= item.cantidad_minima:
                        estado = "bajo_stock"
                    else:
                        estado = "ok"
                    result["drill_down_producto"] = {
                        "nombre": item.nombre_producto,
                        "cantidad_actual": item.cantidad_actual,
                        "cantidad_minima": item.cantidad_minima,
                        "precio_venta": item.precio_venta,
                        "valor_en_stock": round(item.cantidad_actual * (item.precio_venta or 0), 2),
                        "estado": estado,
                    }

        return result

    def _get_clientes_context(self, db: Session, message: str = "") -> Dict[str, Any]:
        clientes = db.query(Cliente).all()
        if not clientes:
            return {"sin_datos": True, "mensaje": "No hay datos de clientes cargados."}

        total = len(clientes)
        activos = sum(1 for c in clientes if c.activo)
        inactivos = total - activos

        tipos: Dict[str, int] = {}
        tipos_activos: Dict[str, int] = {}
        for c in clientes:
            t = c.tipo_cliente or "Sin tipo"
            tipos[t] = tipos.get(t, 0) + 1
            if c.activo:
                tipos_activos[t] = tipos_activos.get(t, 0) + 1

        hace_30 = datetime.now() - timedelta(days=30)
        recientes = sum(1 for c in clientes if c.fecha_registro and c.fecha_registro >= hace_30)

        # Opción 1: nuevos clientes por mes últimos 6 meses
        registros_con_fecha = [c for c in clientes if c.fecha_registro]
        if registros_con_fecha:
            df_cl = pd.DataFrame([{"fecha": c.fecha_registro} for c in registros_con_fecha])
            df_cl["fecha"] = pd.to_datetime(df_cl["fecha"])
            df_cl["mes"] = df_cl["fecha"].dt.to_period("M")
            por_mes = df_cl.groupby("mes").size().sort_index()
            nuevos_por_mes = [
                {"mes": str(p), "nuevos": int(v)} for p, v in por_mes.tail(6).items()
            ]
        else:
            nuevos_por_mes = []

        result = {
            "total_clientes": total,
            "activos": activos,
            "inactivos": inactivos,
            "por_tipo": tipos,
            "registros_ultimos_30_dias": recientes,
            "nuevos_por_mes": nuevos_por_mes,
        }

        # Opción 2: drill-down por tipo de cliente
        if message:
            matched_tipo = _find_entity(message, list(tipos.keys()))
            if matched_tipo and matched_tipo != "Sin tipo":
                result["drill_down_tipo"] = {
                    "tipo": matched_tipo,
                    "total": tipos[matched_tipo],
                    "activos": tipos_activos.get(matched_tipo, 0),
                    "inactivos": tipos[matched_tipo] - tipos_activos.get(matched_tipo, 0),
                }

        return result

    # ── System prompt builder ──────────────────────────────────────

    # Mapeo de número de mes → nombre en español (independiente de locale del OS)
    _MESES_ES = [
        "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        now = datetime.now()
        mes_es = self._MESES_ES[now.month]
        mes_ant_dt = now.replace(day=1) - timedelta(days=1)
        mes_ant_es = self._MESES_ES[mes_ant_dt.month]

        fecha_str = f"{now.day} de {mes_es} de {now.year}"
        hora_str = now.strftime("%H:%M")
        mes_actual = f"{mes_es} {now.year}"
        mes_anterior = f"{mes_ant_es} {mes_ant_dt.year}"

        parts = [
            # 2D — Persona: CFO virtual / socio estratégico
            "Eres el CFO virtual y socio estratégico de esta PYME, integrado en Lumina Ant.",
            "Hablas directamente con el dueño del negocio como si fueran socios: directo, concreto y orientado a decisiones.",
            "Nunca digas 'según los datos proporcionados' ni frases genéricas — ve al grano con números reales.",
            "",
            # 2A — Fecha actual
            f"Fecha de hoy: {fecha_str}, {hora_str} hrs.",
            f"Mes actual: {mes_actual}. Mes anterior: {mes_anterior}.",
            "Usa esto para interpretar correctamente 'este mes', 'el mes pasado', 'año actual', etc.",
            "",
            # 2C — Reglas de formato
            "REGLAS DE RESPUESTA:",
            "- Responde siempre en español.",
            "- Usa los datos reales del contexto. Si un dato no está disponible, dilo en una frase y sigue.",
            "- Formatea montos: $X,XXX.XX. Si supera $1,000,000 abrevia como $X.XM (ej: $1.4M).",
            "- Usa porcentajes en comparativas (ej: 'creció un 18% vs el mes anterior').",
            "- Si hay 3 o más elementos para comparar, usa una tabla markdown.",
            "- Sé conciso: máximo 200 palabras salvo que la pregunta requiera detalle.",
            "- Termina siempre con una recomendación accionable en **negrita** (1-2 líneas máximo).",
            "",
        ]

        if "ventas" in context:
            v = context["ventas"]
            if v.get("sin_datos"):
                parts.append("=== VENTAS ===\nNo hay datos de ventas cargados.\n")
            else:
                parts.append("=== DATOS DE VENTAS ===")
                parts.append(f"- Total ventas: ${v['total_ventas']:,.2f} ({v['num_transacciones']} transacciones)")
                parts.append(f"- Ticket promedio: ${v['ticket_promedio']:,.2f}")
                if v.get("mejor_mes"):
                    parts.append(f"- Mejor mes: {v['mejor_mes']['mes']} (${v['mejor_mes']['monto']:,.2f})")
                if v.get("peor_mes"):
                    parts.append(f"- Peor mes: {v['peor_mes']['mes']} (${v['peor_mes']['monto']:,.2f})")
                if v.get("top_productos"):
                    prods = ", ".join(f"{p['nombre']} (${p['monto']:,.2f})" for p in v["top_productos"])
                    parts.append(f"- Top productos (hasta 20): {prods}")
                if v.get("top_categorias"):
                    cats = ", ".join(f"{c['nombre']} (${c['monto']:,.2f})" for c in v["top_categorias"])
                    parts.append(f"- Top categorías (hasta 10): {cats}")
                if v.get("tendencia_mensual"):
                    trend = ", ".join(f"{t['mes']}: ${t['monto']:,.2f}" for t in v["tendencia_mensual"])
                    parts.append(f"- Tendencia mensual (12 meses): {trend}")
                if v.get("semanas_recientes"):
                    sem = ", ".join(f"{s['semana']}: ${s['monto']:,.2f}" for s in v["semanas_recientes"])
                    parts.append(f"- Ventas semanales recientes: {sem}")
                # Drill-down producto
                if v.get("drill_down_producto"):
                    dd = v["drill_down_producto"]
                    parts.append(f"\n-- DETALLE PRODUCTO: {dd['nombre']} --")
                    parts.append(f"  Total vendido: ${dd['total']:,.2f} ({dd['transacciones']} transacciones, {dd['cantidad_total']} unidades)")
                    parts.append(f"  Ticket promedio: ${dd['ticket_promedio']:,.2f}")
                    if dd.get("tendencia_mensual"):
                        t = ", ".join(f"{x['mes']}: ${x['monto']:,.2f}" for x in dd["tendencia_mensual"])
                        parts.append(f"  Historial mensual: {t}")
                # Drill-down período
                if v.get("drill_down_periodo"):
                    dd = v["drill_down_periodo"]
                    parts.append(f"\n-- DETALLE MES {dd['periodo']} (ventas) --")
                    parts.append(f"  Total: ${dd['total']:,.2f} ({dd['transacciones']} transacciones)")
                    parts.append(f"  Ticket promedio: ${dd['ticket_promedio']:,.2f}")
                    if dd.get("top_productos"):
                        tp = ", ".join(f"{p['nombre']} (${p['monto']:,.2f})" for p in dd["top_productos"])
                        parts.append(f"  Top productos ese mes: {tp}")
                    if dd.get("por_semana"):
                        ps = ", ".join(f"sem {s['semana']}: ${s['monto']:,.2f}" for s in dd["por_semana"])
                        parts.append(f"  Por semana: {ps}")
                parts.append("")

        if "gastos" in context:
            g = context["gastos"]
            if g.get("sin_datos"):
                parts.append("=== GASTOS ===\nNo hay datos de gastos cargados.\n")
            else:
                parts.append("=== DATOS DE GASTOS ===")
                parts.append(f"- Total gastos: ${g['total_gastos']:,.2f} ({g['num_transacciones']} transacciones)")
                parts.append(f"- Gasto promedio: ${g['gasto_promedio']:,.2f}")
                if g.get("top_categorias"):
                    cats = ", ".join(f"{c['nombre']} (${c['monto']:,.2f})" for c in g["top_categorias"])
                    parts.append(f"- Top categorías: {cats}")
                if g.get("top_proveedores"):
                    provs = ", ".join(f"{p['nombre']} (${p['monto']:,.2f})" for p in g["top_proveedores"])
                    parts.append(f"- Top proveedores (hasta 10): {provs}")
                if g.get("gasto_mas_grande"):
                    gm = g["gasto_mas_grande"]
                    parts.append(f"- Gasto más grande: {gm['descripcion']} (${gm['monto']:,.2f}, {gm['categoria']})")
                if g.get("tendencia_mensual"):
                    trend = ", ".join(f"{t['mes']}: ${t['monto']:,.2f}" for t in g["tendencia_mensual"])
                    parts.append(f"- Tendencia mensual (12 meses): {trend}")
                # Drill-down proveedor
                if g.get("drill_down_proveedor"):
                    dd = g["drill_down_proveedor"]
                    parts.append(f"\n-- DETALLE PROVEEDOR: {dd['nombre']} --")
                    parts.append(f"  Total pagado: ${dd['total']:,.2f} ({dd['transacciones']} transacciones)")
                    if dd.get("categorias"):
                        cats = ", ".join(f"{c['nombre']} (${c['monto']:,.2f})" for c in dd["categorias"])
                        parts.append(f"  Categorías: {cats}")
                    if dd.get("ultimo_gasto"):
                        ug = dd["ultimo_gasto"]
                        parts.append(f"  Último gasto: {ug['descripcion']} (${ug['monto']:,.2f}) el {ug['fecha']}")
                # Drill-down período
                if g.get("drill_down_periodo"):
                    dd = g["drill_down_periodo"]
                    parts.append(f"\n-- DETALLE MES {dd['periodo']} (gastos) --")
                    parts.append(f"  Total: ${dd['total']:,.2f} ({dd['transacciones']} transacciones)")
                    if dd.get("top_categorias"):
                        tc = ", ".join(f"{c['nombre']} (${c['monto']:,.2f})" for c in dd["top_categorias"])
                        parts.append(f"  Top categorías ese mes: {tc}")
                    if dd.get("top_proveedores"):
                        tp = ", ".join(f"{p['nombre']} (${p['monto']:,.2f})" for p in dd["top_proveedores"])
                        parts.append(f"  Top proveedores ese mes: {tp}")
                parts.append("")

        if "inventario" in context:
            inv = context["inventario"]
            if inv.get("sin_datos"):
                parts.append("=== INVENTARIO ===\nNo hay datos de inventario cargados.\n")
            else:
                parts.append("=== DATOS DE INVENTARIO ===")
                parts.append(f"- Total productos: {inv['total_productos']}")
                parts.append(f"- Valor total inventario: ${inv['valor_total_inventario']:,.2f}")
                parts.append(f"- Productos bajo stock: {inv['num_bajo_stock']}")
                parts.append(f"- Productos sin stock: {inv['num_sin_stock']}")
                if inv.get("productos_sin_stock"):
                    parts.append(f"- Sin stock: {', '.join(inv['productos_sin_stock'])}")
                if inv.get("productos_bajo_stock"):
                    bajos = ", ".join(
                        f"{p['nombre']} ({p['actual']}/{p['minimo']})"
                        for p in inv["productos_bajo_stock"]
                    )
                    parts.append(f"- Bajo stock: {bajos}")
                if inv.get("top_por_valor"):
                    top = ", ".join(f"{p['nombre']} (${p['valor']:,.2f})" for p in inv["top_por_valor"])
                    parts.append(f"- Top por valor (hasta 10): {top}")
                # Drill-down producto inventario
                if inv.get("drill_down_producto"):
                    dd = inv["drill_down_producto"]
                    estado_txt = {"ok": "OK", "bajo_stock": "⚠️ Bajo stock", "sin_stock": "🚨 Sin stock"}.get(dd["estado"], dd["estado"])
                    parts.append(f"\n-- DETALLE PRODUCTO EN INVENTARIO: {dd['nombre']} --")
                    parts.append(f"  Cantidad actual: {dd['cantidad_actual']} | Mínimo: {dd['cantidad_minima']} | Estado: {estado_txt}")
                    if dd.get("precio_venta"):
                        parts.append(f"  Precio venta: ${dd['precio_venta']:,.2f} | Valor en stock: ${dd['valor_en_stock']:,.2f}")
                parts.append("")

        if "clientes" in context:
            cl = context["clientes"]
            if cl.get("sin_datos"):
                parts.append("=== CLIENTES ===\nNo hay datos de clientes cargados.\n")
            else:
                parts.append("=== DATOS DE CLIENTES ===")
                parts.append(f"- Total clientes: {cl['total_clientes']}")
                parts.append(f"- Activos: {cl['activos']}, Inactivos: {cl['inactivos']}")
                if cl.get("por_tipo"):
                    tipos = ", ".join(f"{t}: {n}" for t, n in cl["por_tipo"].items())
                    parts.append(f"- Por tipo: {tipos}")
                parts.append(f"- Registros últimos 30 días: {cl.get('registros_ultimos_30_dias', 0)}")
                if cl.get("nuevos_por_mes"):
                    npm = ", ".join(f"{x['mes']}: {x['nuevos']}" for x in cl["nuevos_por_mes"])
                    parts.append(f"- Nuevos clientes por mes (6 meses): {npm}")
                # Drill-down tipo
                if cl.get("drill_down_tipo"):
                    dd = cl["drill_down_tipo"]
                    parts.append(f"\n-- DETALLE TIPO CLIENTE: {dd['tipo']} --")
                    parts.append(f"  Total: {dd['total']} | Activos: {dd['activos']} | Inactivos: {dd['inactivos']}")
                parts.append("")

        # 2B — Rentabilidad cruzada (solo si hay ventas Y gastos con datos reales)
        v = context.get("ventas", {})
        g = context.get("gastos", {})
        if v and g and not v.get("sin_datos") and not g.get("sin_datos"):
            total_v = v.get("total_ventas", 0)
            total_g = g.get("total_gastos", 0)
            if total_v > 0:
                margen_bruto = total_v - total_g
                margen_pct = margen_bruto / total_v * 100
                ratio_gasto = total_g / total_v * 100
                parts.append("=== RENTABILIDAD ESTIMADA ===")
                parts.append(f"- Ingresos totales: ${total_v:,.2f}")
                parts.append(f"- Gastos totales: ${total_g:,.2f} ({ratio_gasto:.1f}% de las ventas)")
                parts.append(f"- Margen bruto estimado: ${margen_bruto:,.2f} ({margen_pct:.1f}%)")
                if margen_pct < 0:
                    parts.append("⚠️ ALERTA: Los gastos superan los ingresos — el negocio opera en pérdida.")
                elif margen_pct < 15:
                    parts.append("⚠️ Margen ajustado: menor al 15%, hay presión financiera.")
                elif margen_pct >= 40:
                    parts.append("✅ Margen saludable: por encima del 40%.")
                parts.append("(Nota: estimación basada en registros cargados, no incluye costos no registrados.)")
                parts.append("")

        return "\n".join(parts)

    # ── Demo mode ──────────────────────────────────────────────────

    def _demo_response(
        self,
        user_message: str,
        intents: List[str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a template-based response using real computed data."""
        parts = ["**MODO DEMO** — Respuesta simulada con datos reales:\n"]

        if "ventas" in context:
            v = context["ventas"]
            if v.get("sin_datos"):
                parts.append("📈 No hay datos de ventas cargados todavía.")
            else:
                parts.append(f"📈 Tienes **{v['num_transacciones']}** transacciones de venta por un total de **${v['total_ventas']:,.2f}**.")
                parts.append(f"Tu ticket promedio es **${v['ticket_promedio']:,.2f}**.")
                if v.get("top_productos"):
                    parts.append(f"Tu producto estrella es **{v['top_productos'][0]['nombre']}** con ${v['top_productos'][0]['monto']:,.2f}.")
                if v.get("mejor_mes"):
                    parts.append(f"Tu mejor mes fue **{v['mejor_mes']['mes']}** con ${v['mejor_mes']['monto']:,.2f}.")
                if v.get("drill_down_producto"):
                    dd = v["drill_down_producto"]
                    parts.append(f"\nSobre **{dd['nombre']}**: ${dd['total']:,.2f} en {dd['transacciones']} ventas ({dd['cantidad_total']} unidades).")
                if v.get("drill_down_periodo"):
                    dd = v["drill_down_periodo"]
                    parts.append(f"\nEn **{dd['periodo']}**: ${dd['total']:,.2f} en {dd['transacciones']} ventas.")

        if "gastos" in context:
            g = context["gastos"]
            if g.get("sin_datos"):
                parts.append("\n💸 No hay datos de gastos cargados todavía.")
            else:
                parts.append(f"\n💸 Tienes **{g['num_transacciones']}** registros de gastos por **${g['total_gastos']:,.2f}** en total.")
                if g.get("top_categorias"):
                    parts.append(f"La categoría con mayor gasto es **{g['top_categorias'][0]['nombre']}** (${g['top_categorias'][0]['monto']:,.2f}).")
                if g.get("drill_down_proveedor"):
                    dd = g["drill_down_proveedor"]
                    parts.append(f"\nSobre proveedor **{dd['nombre']}**: ${dd['total']:,.2f} en {dd['transacciones']} transacciones.")

        if "inventario" in context:
            inv = context["inventario"]
            if inv.get("sin_datos"):
                parts.append("\n📦 No hay datos de inventario cargados todavía.")
            else:
                parts.append(f"\n📦 Tienes **{inv['total_productos']}** productos en inventario con un valor de **${inv['valor_total_inventario']:,.2f}**.")
                if inv["num_bajo_stock"] > 0:
                    parts.append(f"⚠️ **{inv['num_bajo_stock']}** productos necesitan reabastecimiento.")
                if inv["num_sin_stock"] > 0:
                    parts.append(f"🚨 **{inv['num_sin_stock']}** productos están sin stock.")
                if inv.get("drill_down_producto"):
                    dd = inv["drill_down_producto"]
                    estado_txt = {"ok": "en stock", "bajo_stock": "bajo stock", "sin_stock": "sin stock"}.get(dd["estado"], dd["estado"])
                    parts.append(f"\n**{dd['nombre']}**: {dd['cantidad_actual']} unidades — {estado_txt}.")

        if "clientes" in context:
            cl = context["clientes"]
            if cl.get("sin_datos"):
                parts.append("\n👥 No hay datos de clientes cargados todavía.")
            else:
                parts.append(f"\n👥 Tienes **{cl['total_clientes']}** clientes registrados: **{cl['activos']}** activos y **{cl['inactivos']}** inactivos.")

        if not context:
            parts.append("No se encontraron datos cargados. Importa archivos CSV desde la sección de Configuración para empezar.")

        settings = get_settings()
        provider = settings.ai_provider.upper()
        key_map = {"CLAUDE": "ANTHROPIC_API_KEY", "OPENAI": "OPENAI_API_KEY", "GEMINI": "GOOGLE_API_KEY"}
        key_name = key_map.get(provider, "API_KEY")
        parts.append(f"\n---\n🔑 Configura **{key_name}** en `.env` para respuestas personalizadas con IA ({provider}).")

        return {
            "role": "assistant",
            "content": "\n".join(parts),
            "intents": intents,
            "data_sources": list(context.keys()),
        }

    # ── Analytics ──────────────────────────────────────────────────

    def _log_interaction(
        self,
        *,
        mode: str,                    # "chat" | "stream"
        message: str,
        intents: List[str],
        context: Dict[str, Any],
        response_text: str,
        duration_ms: int,
        usage: Optional[Dict] = None,
        demo_mode: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """
        Escribe una entrada JSONL en backend/logs/chat_YYYY-MM-DD.jsonl.
        Las preguntas que la IA no pudo resolver se marcan con NEEDS_REVIEW=true.
        """
        unresolvable, signal = _detect_unresolvable(response_text) if response_text else (False, None)

        # Detectar qué drill-downs se activaron
        drill_downs = []
        for table, ctx in context.items():
            for key in ctx:
                if key.startswith("drill_down_"):
                    drill_downs.append(f"{table}.{key}")

        # Estimar tokens si no tenemos los exactos
        if not usage:
            # ~4 chars por token (estimación conservadora)
            settings = get_settings()
            sys_prompt_est = len(self._build_system_prompt(context)) // 4
            resp_est = len(response_text) // 4 if response_text else 0
            usage = {
                "input_tokens": sys_prompt_est,
                "output_tokens": resp_est,
                "total_tokens": sys_prompt_est + resp_est,
                "source": "estimated",
            }

        settings = get_settings()
        entry: Dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "demo_mode": demo_mode,
            "provider": settings.ai_provider if not demo_mode else "demo",
            "model": (
                settings.claude_model if settings.ai_provider == "claude"
                else settings.openai_model if settings.ai_provider == "openai"
                else settings.gemini_model
            ) if not demo_mode else "demo",
            "msg": message,
            "response": response_text or "",
            "intents": intents,
            "data_sources": list(context.keys()),
            "drill_downs": drill_downs,
            "tokens": usage,
            "duration_ms": duration_ms,
            "unresolvable": unresolvable,
        }

        if unresolvable:
            entry["unresolvable_signal"] = signal
            entry["NEEDS_REVIEW"] = True   # fácil de grep: grep "NEEDS_REVIEW" chat_*.jsonl

        if error:
            entry["error"] = error
            entry["NEEDS_REVIEW"] = True

        _write_analytics(entry)

        # También loguear en el logger estándar para consola
        flag = " ⚠️ NEEDS_REVIEW" if entry.get("NEEDS_REVIEW") else ""
        logger.info(
            f"[ANALYTICS]{flag} intents={intents} tokens={usage.get('total_tokens', '?')} "
            f"({usage.get('source', '?')}) dur={duration_ms}ms | {message[:80]}"
        )

    # ── Streaming chat ─────────────────────────────────────────────

    async def stream_chat(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        db: Session,
    ) -> AsyncIterator[str]:
        """
        Versión streaming de chat(). Yields fragmentos SSE:
          data: {"type": "delta", "content": "..."}
          data: {"type": "done",  "intents": [...], "data_sources": [...], "suggested_followups": [...]}
          data: {"type": "error", "content": "..."}   ← solo en caso de excepción
        """
        t0 = time.monotonic()
        intents = self._classify_intent(user_message)
        logger.info(f"Stream chat intents: {intents}")

        context: Dict[str, Any] = {}
        tables_needed: set = set()
        for intent in intents:
            for table in INTENT_MAP.get(intent, {}).get("tables", []):
                tables_needed.add(table)
        for table in tables_needed:
            ctx = self._get_table_context(table, db, user_message)
            if ctx:
                context[table] = ctx

        followups = self.get_followups(intents, list(context.keys()))
        data_sources = list(context.keys())

        if self.demo_mode:
            result = self._demo_response(user_message, intents, context)
            content = result["content"]
            yield f"data: {json.dumps({'type': 'delta', 'content': content})}\n\n"
            # Estimar tokens para el demo
            sys_prompt_est = len(self._build_system_prompt(context)) // 4
            resp_est = len(content) // 4
            usage = {
                "input_tokens": sys_prompt_est,
                "output_tokens": resp_est,
                "total_tokens": sys_prompt_est + resp_est,
                "source": "estimated",
            }
            yield f"data: {json.dumps({'type': 'done', 'intents': intents, 'data_sources': data_sources, 'suggested_followups': followups, 'usage': usage})}\n\n"
            self._log_interaction(
                mode="stream", message=user_message, intents=intents, context=context,
                response_text=content, duration_ms=int((time.monotonic() - t0) * 1000),
                demo_mode=True,
            )
            return

        system_prompt = self._build_system_prompt(context)
        messages = []
        for msg in history[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        accumulated = []
        try:
            async for delta in self.provider.stream_completion(
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=1500,
            ):
                accumulated.append(delta)
                yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"
            full_response = "".join(accumulated)
            usage = self.provider.get_last_usage()
            yield f"data: {json.dumps({'type': 'done', 'intents': intents, 'data_sources': data_sources, 'suggested_followups': followups, 'usage': usage})}\n\n"
            self._log_interaction(
                mode="stream", message=user_message, intents=intents, context=context,
                response_text=full_response, duration_ms=int((time.monotonic() - t0) * 1000),
                usage=usage,
            )
        except Exception as e:
            logger.error(f"Error en stream {self.provider.provider_name}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            self._log_interaction(
                mode="stream", message=user_message, intents=intents, context=context,
                response_text="".join(accumulated), duration_ms=int((time.monotonic() - t0) * 1000),
                error=str(e),
            )

    # ── Follow-up suggestions ──────────────────────────────────────

    @staticmethod
    def get_followups(intents: List[str], data_sources: List[str]) -> List[str]:
        """Generate follow-up suggestions based on intents used."""
        suggestions = []
        seen = set()
        for intent in intents:
            for followup in FOLLOWUPS.get(intent, []):
                if followup not in seen:
                    suggestions.append(followup)
                    seen.add(followup)
                if len(suggestions) >= 3:
                    break
            if len(suggestions) >= 3:
                break

        if not suggestions:
            for followup in FOLLOWUPS["general"]:
                suggestions.append(followup)

        return suggestions[:3]


# ── Singleton (cache de contexto) ─────────────────────────────────

_service_instance: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """
    Retorna la instancia singleton de ChatService.
    El provider de IA (y sus conexiones) se inicializan una sola vez
    y se reutilizan en todas las requests.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ChatService()
    return _service_instance
