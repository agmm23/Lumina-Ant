"""
Lumina_Ant - Servicio de Chat/Copilot IA (enfoque Text-to-SQL)
Pipeline: Generar SQL → Ejecutar contra SQLite → Interpretar con IA
"""

import json
import os
import time
import re
from typing import AsyncIterator, List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import get_settings
from app.services.ai_provider import get_ai_provider, AIProvider
from datetime import datetime
import logging

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


def _detect_unresolvable(response: str) -> Tuple[bool, Optional[str]]:
    """Detecta si la IA no pudo resolver la pregunta. Retorna (es_irresoluble, señal)."""
    import unicodedata
    normalized = response.lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = re.sub(r"[\u0300-\u036f]", "", normalized)
    for pattern, label in _UNRESOLVABLE_PATTERNS:
        if re.search(pattern, normalized):
            return True, label
    return False, None


# ── Esquema de la base de datos ──────────────────────────────────
DB_SCHEMA = """Tablas disponibles en la base de datos SQLite:

TABLA: ventas — Transacciones de venta
  id               INTEGER  clave primaria
  user_id          INTEGER  identificador del usuario propietario
  fecha            DATETIME fecha y hora de la venta
  producto_id      TEXT     identificador del producto
  nombre_producto  TEXT     nombre descriptivo del producto
  cantidad         INTEGER  unidades vendidas
  precio_unitario  FLOAT    precio por unidad
  monto_total      FLOAT    total de la venta (cantidad × precio_unitario)
  cliente_id       TEXT     identificador del cliente (puede ser NULL)
  categoria        TEXT     categoría del producto (puede ser NULL)

TABLA: gastos — Gastos operativos
  id               INTEGER  clave primaria
  user_id          INTEGER  identificador del usuario propietario
  fecha            DATETIME fecha del gasto
  descripcion      TEXT     descripción del gasto
  categoria        TEXT     'personal' | 'servicios' | 'insumos' | 'marketing' | 'otros'
  monto            FLOAT    importe del gasto
  nombre_proveedor TEXT     nombre del proveedor (puede ser NULL)
  tipo_pago        TEXT     'efectivo' | 'transferencia' | 'tarjeta' | 'cheque' (puede ser NULL)
  numero_factura   TEXT     (puede ser NULL)
  notas            TEXT     (puede ser NULL)

TABLA: inventario — Stock de productos
  id               INTEGER  clave primaria
  user_id          INTEGER  identificador del usuario propietario
  producto_id      TEXT     identificador único del producto (por usuario)
  nombre_producto  TEXT     nombre del producto
  descripcion      TEXT     descripción (puede ser NULL)
  categoria        TEXT     (puede ser NULL)
  cantidad_actual  INTEGER  unidades en stock
  cantidad_minima  INTEGER  umbral de alerta de bajo stock (puede ser NULL)
  unidad_medida    TEXT     'unidades' | 'kg' | 'litros' | etc. (puede ser NULL)
  precio_compra    FLOAT    (puede ser NULL)
  precio_venta     FLOAT    (puede ser NULL)
  proveedor_id     TEXT     (puede ser NULL)
  ubicacion        TEXT     ubicación en almacén (puede ser NULL)

TABLA: clientes — Clientes del negocio
  id               INTEGER  clave primaria
  user_id          INTEGER  identificador del usuario propietario
  cliente_id       TEXT     identificador único del cliente (por usuario)
  nombre           TEXT     nombre completo
  email            TEXT     (puede ser NULL)
  telefono         TEXT     (puede ser NULL)
  ciudad           TEXT     (puede ser NULL)
  tipo_cliente     TEXT     'minorista' | 'mayorista' | 'corporativo' (puede ser NULL)
  fecha_registro   DATETIME fecha de alta del cliente
  activo           BOOLEAN  1 = activo, 0 = inactivo
  notas            TEXT     (puede ser NULL)
"""

# ── Preguntas sugeridas y follow-ups ─────────────────────────────
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
}


# ── Helpers SQL ──────────────────────────────────────────────────

# Prompt estático para generación SQL — se cachea en Claude (cache_control: ephemeral).
# Contiene solo partes invariables entre requests: esquema + reglas.
_SQL_SYSTEM_PROMPT = f"""Eres un experto en SQL para SQLite trabajando con una base de datos de una PYME.

Estructura de la base de datos:
{DB_SCHEMA}
REGLAS ESTRICTAS:
1. Solo usa SELECT. Nunca INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, PRAGMA.
2. SIEMPRE filtra por el user_id que se indica en el mensaje en CADA tabla que consultes. Sin excepción.
3. Usa funciones SQLite estándar: strftime(), date(), julianday(), COALESCE(), IFNULL(), ROUND().
4. Para "este mes": WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
5. Para "el mes pasado": WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', date('now', 'start of month', '-1 month'))
6. Para "este año": WHERE strftime('%Y', fecha) = strftime('%Y', 'now')
7. Redondea montos con ROUND(..., 2).
8. Usa LIMIT 50 por defecto, salvo que el usuario pida explícitamente todos los registros.
9. Si la pregunta no corresponde a ninguna tabla disponible, responde exactamente con la palabra: NO_SQL

Genera UNA SOLA consulta SQL SELECT. Responde ÚNICAMENTE con la sentencia SQL (sin explicaciones, sin markdown, sin ```)."""


def _build_sql_user_message(question: str, now: str, user_id: int) -> str:
    """Parte dinámica del prompt SQL: sólo los datos variables por request."""
    return f"Fecha y hora actual: {now}\nID del usuario actual: {user_id}\nPregunta: \"{question}\""


def _is_safe_sql(sql: str) -> bool:
    """Verifica que el SQL sea solo SELECT sin operaciones peligrosas."""
    sql_clean = sql.strip().upper()
    if not sql_clean.startswith("SELECT"):
        return False
    dangerous = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "ATTACH", "PRAGMA", "EXEC"}
    tokens = set(re.split(r"\W+", sql_clean))
    return not (tokens & dangerous)


def _detect_tables_used(sql: str) -> List[str]:
    """Detecta qué tablas del negocio aparecen en el SQL."""
    sql_upper = sql.upper()
    return [t for t in ["ventas", "gastos", "inventario", "clientes"] if t.upper() in sql_upper]


def _build_interpretation_prompt(question: str, sql: str, rows: List[Dict]) -> str:
    """Construye el prompt para interpretar los resultados SQL en lenguaje natural."""
    rows_str = json.dumps(rows, ensure_ascii=False, default=str, indent=2)
    return f"""El usuario de un dashboard de negocio preguntó: "{question}"

Para responder, se ejecutó esta consulta SQL:
{sql}

Resultados ({len(rows)} filas):
{rows_str}

Responde en español de forma clara y concisa. Incluye los números exactos del resultado.
Usa formato markdown cuando ayude: tablas para comparar 3 o más elementos, **negrita** para cifras clave.
Si los resultados están vacíos, explica que no hay datos disponibles para esa consulta.
Termina siempre con una recomendación accionable en **negrita** (máximo 2 líneas).
Máximo 200 palabras."""


# ── Helpers de uso de tokens ─────────────────────────────────────

def _merge_usage(usage_a: Dict, usage_b: Dict) -> Dict:
    """Suma el usage de dos llamadas a la IA y retorna el total acumulado."""
    inp = usage_a.get("input_tokens", 0) + usage_b.get("input_tokens", 0)
    out = usage_a.get("output_tokens", 0) + usage_b.get("output_tokens", 0)
    cache_created = usage_a.get("cache_creation_input_tokens", 0) + usage_b.get("cache_creation_input_tokens", 0)
    cache_read = usage_a.get("cache_read_input_tokens", 0) + usage_b.get("cache_read_input_tokens", 0)
    source_a = usage_a.get("source", "estimated")
    source_b = usage_b.get("source", "estimated")
    source = "exact" if source_a == "exact" and source_b == "exact" else "partial"
    result = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out, "source": source}
    if cache_created:
        result["cache_creation_input_tokens"] = cache_created
    if cache_read:
        result["cache_read_input_tokens"] = cache_read
    return result


# ── Servicio principal ───────────────────────────────────────────

class ChatService:
    """Servicio de Chat/Copilot con pipeline Text-to-SQL."""

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
        user_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje del usuario con el pipeline Text-to-SQL:
        1) Genera SQL desde la pregunta
        2) Ejecuta el SQL en SQLite
        3) Interpreta los resultados con IA
        """
        t0 = time.monotonic()

        if self.demo_mode:
            result = self._demo_response(user_message)
            self._log_interaction(
                mode="chat", message=user_message, sql=None, data_sources=[],
                response_text=result["content"],
                duration_ms=int((time.monotonic() - t0) * 1000), demo_mode=True,
            )
            return result

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ── Llamada 1: generar SQL ────────────────────────────────
        # El system prompt (_SQL_SYSTEM_PROMPT) es estático → se cachea en Claude.
        # Solo el user message varía por request (pregunta + fecha + user_id).
        sql_user_msg = _build_sql_user_message(user_message, now, user_id)
        try:
            sql_raw = self.provider.chat_completion(
                system_prompt=_SQL_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": sql_user_msg}],
                max_tokens=400,
            )
            sql_gen_usage = self.provider.get_last_usage()
        except Exception as e:
            logger.error(f"Error generando SQL via {self.provider.provider_name}: {e}")
            return {
                "role": "assistant",
                "content": f"Lo siento, hubo un error al procesar tu pregunta. Detalle: {e}",
                "intents": [],
                "data_sources": [],
            }

        # Limpiar posibles artefactos de markdown que algunos modelos añaden
        sql = sql_raw.strip().strip("`").strip()
        sql = re.sub(r"^(sql\s*\n?)", "", sql, flags=re.IGNORECASE).strip()

        if sql.upper() == "NO_SQL" or not _is_safe_sql(sql):
            content = (
                "No pude generar una consulta válida para esa pregunta. "
                "¿Puedes reformularla enfocándote en ventas, gastos, inventario o clientes?"
            )
            self._log_interaction(
                mode="chat", message=user_message, sql=sql, data_sources=[],
                response_text=content, duration_ms=int((time.monotonic() - t0) * 1000),
            )
            return {"role": "assistant", "content": content, "intents": [], "data_sources": []}

        # ── Ejecutar SQL ──────────────────────────────────────────
        try:
            rows = self._execute_sql(sql, db)
        except Exception as e:
            logger.error(f"Error ejecutando SQL: {e}\nSQL: {sql}")
            content = "Hubo un error al ejecutar la consulta. ¿Puedes reformular la pregunta?"
            self._log_interaction(
                mode="chat", message=user_message, sql=sql, data_sources=[],
                response_text=content, duration_ms=int((time.monotonic() - t0) * 1000), error=str(e),
            )
            return {"role": "assistant", "content": content, "intents": [], "data_sources": []}

        # ── Llamada 2: interpretar resultados ─────────────────────
        interp_prompt = _build_interpretation_prompt(user_message, sql, rows)
        try:
            content = self.provider.chat_completion(
                system_prompt="Eres un analista de negocios para PYMEs hispanohablantes. Responde siempre en español.",
                messages=[{"role": "user", "content": interp_prompt}],
                max_tokens=800,
            )
        except Exception as e:
            logger.error(f"Error interpretando resultados via {self.provider.provider_name}: {e}")
            return {
                "role": "assistant",
                "content": f"Obtuve los datos pero hubo un error al interpretarlos. Detalle: {e}",
                "intents": [],
                "data_sources": [],
            }

        tables = _detect_tables_used(sql)
        interp_usage = self.provider.get_last_usage()
        # Acumular tokens de ambas llamadas (SQL gen + interpretación)
        usage = _merge_usage(sql_gen_usage, interp_usage)
        cache_info = (
            f" cache_read={usage['cache_read_input_tokens']}"
            if usage.get("cache_read_input_tokens") else ""
        )
        logger.info(
            f"Chat SQL→interp via {self.provider.provider_name} "
            f"({len(rows)} rows) tokens={usage.get('total_tokens', '?')} "
            f"[sql_gen={sql_gen_usage.get('total_tokens','?')} interp={interp_usage.get('total_tokens','?')}]"
            f"{cache_info}"
        )

        self._log_interaction(
            mode="chat", message=user_message, sql=sql, data_sources=tables,
            response_text=content, duration_ms=int((time.monotonic() - t0) * 1000), usage=usage,
        )

        return {
            "role": "assistant",
            "content": content,
            "intents": tables,
            "data_sources": tables,
        }

    def _execute_sql(self, sql: str, db: Session) -> List[Dict]:
        """Ejecuta el SQL de forma segura y retorna hasta 100 filas."""
        result = db.execute(text(sql))
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchmany(100)]

    # ── Streaming chat ─────────────────────────────────────────────

    async def stream_chat(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        db: Session,
        user_id: int = 1,
    ) -> AsyncIterator[str]:
        """
        Versión streaming del pipeline Text-to-SQL.
        Las fases 1 (generar SQL) y 2 (ejecutar) son síncronas.
        La fase 3 (interpretar) se transmite en streaming.

        Yields fragmentos SSE:
          data: {"type": "delta", "content": "..."}
          data: {"type": "done",  "intents": [...], "data_sources": [...], ...}
          data: {"type": "error", "content": "..."}
        """
        t0 = time.monotonic()

        if self.demo_mode:
            result = self._demo_response(user_message)
            content = result["content"]
            yield f"data: {json.dumps({'type': 'delta', 'content': content})}\n\n"
            usage = {
                "input_tokens": 0,
                "output_tokens": len(content) // 4,
                "total_tokens": len(content) // 4,
                "source": "estimated",
            }
            yield f"data: {json.dumps({'type': 'done', 'intents': [], 'data_sources': [], 'suggested_followups': FOLLOWUPS['general'], 'usage': usage})}\n\n"
            self._log_interaction(
                mode="stream", message=user_message, sql=None, data_sources=[],
                response_text=content, duration_ms=int((time.monotonic() - t0) * 1000), demo_mode=True,
            )
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ── Fase 1: generar SQL (síncrono) ────────────────────────
        # System prompt estático → cacheado; user message dinámico por request.
        sql_user_msg = _build_sql_user_message(user_message, now, user_id)
        try:
            sql_raw = self.provider.chat_completion(
                system_prompt=_SQL_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": sql_user_msg}],
                max_tokens=400,
            )
            sql_gen_usage = self.provider.get_last_usage()
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            return

        sql = sql_raw.strip().strip("`").strip()
        sql = re.sub(r"^(sql\s*\n?)", "", sql, flags=re.IGNORECASE).strip()

        if sql.upper() == "NO_SQL" or not _is_safe_sql(sql):
            msg = (
                "No pude generar una consulta válida para esa pregunta. "
                "¿Puedes reformularla enfocándote en ventas, gastos, inventario o clientes?"
            )
            yield f"data: {json.dumps({'type': 'delta', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'intents': [], 'data_sources': [], 'suggested_followups': FOLLOWUPS['general'], 'usage': {}})}\n\n"
            return

        # ── Fase 2: ejecutar SQL (síncrono) ──────────────────────
        try:
            rows = self._execute_sql(sql, db)
        except Exception as e:
            logger.error(f"Error ejecutando SQL en stream: {e}\nSQL: {sql}")
            msg = "Hubo un error al ejecutar la consulta. ¿Puedes reformular la pregunta?"
            yield f"data: {json.dumps({'type': 'delta', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'intents': [], 'data_sources': [], 'suggested_followups': FOLLOWUPS['general'], 'usage': {}})}\n\n"
            return

        # ── Fase 3: interpretar en streaming ─────────────────────
        tables = _detect_tables_used(sql)
        followups = self.get_followups(tables, tables)
        interp_prompt = _build_interpretation_prompt(user_message, sql, rows)
        system = "Eres un analista de negocios para PYMEs hispanohablantes. Responde siempre en español."
        messages = [{"role": "user", "content": interp_prompt}]

        accumulated: List[str] = []
        try:
            async for delta in self.provider.stream_completion(
                system_prompt=system,
                messages=messages,
                max_tokens=800,
            ):
                accumulated.append(delta)
                yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"

            full_response = "".join(accumulated)
            interp_usage = self.provider.get_last_usage()
            # Acumular tokens de ambas llamadas (SQL gen + interpretación)
            usage = _merge_usage(sql_gen_usage, interp_usage)
            yield f"data: {json.dumps({'type': 'done', 'intents': tables, 'data_sources': tables, 'suggested_followups': followups, 'usage': usage})}\n\n"
            self._log_interaction(
                mode="stream", message=user_message, sql=sql, data_sources=tables,
                response_text=full_response, duration_ms=int((time.monotonic() - t0) * 1000), usage=usage,
            )
        except Exception as e:
            logger.error(f"Error en stream {self.provider.provider_name}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            self._log_interaction(
                mode="stream", message=user_message, sql=sql, data_sources=tables,
                response_text="".join(accumulated), duration_ms=int((time.monotonic() - t0) * 1000), error=str(e),
            )

    # ── Follow-up suggestions ──────────────────────────────────────

    @staticmethod
    def get_followups(intents: List[str], data_sources: List[str]) -> List[str]:
        """Genera sugerencias de follow-up basadas en las tablas usadas."""
        suggestions: List[str] = []
        seen: set = set()
        sources = intents or data_sources or ["general"]
        for source in sources:
            for followup in FOLLOWUPS.get(source, []):
                if followup not in seen:
                    suggestions.append(followup)
                    seen.add(followup)
                if len(suggestions) >= 3:
                    break
            if len(suggestions) >= 3:
                break
        if not suggestions:
            suggestions = FOLLOWUPS["general"]
        return suggestions[:3]

    # ── Demo mode ──────────────────────────────────────────────────

    def _demo_response(self, user_message: str) -> Dict[str, Any]:
        settings = get_settings()
        provider = settings.ai_provider.upper()
        key_map = {"CLAUDE": "ANTHROPIC_API_KEY", "OPENAI": "OPENAI_API_KEY", "GEMINI": "GOOGLE_API_KEY"}
        key_name = key_map.get(provider, "API_KEY")
        content = (
            "**MODO DEMO** — El copiloto IA está desactivado.\n\n"
            "Este sistema usa un enfoque **Text-to-SQL**: la IA genera consultas SQL sobre tu base de datos "
            "en lugar de recibir datos raw, lo que hace las respuestas más precisas y eficientes.\n\n"
            f"Para activarlo, configura **{key_name}** en el archivo `.env` y reinicia el servidor."
        )
        return {"role": "assistant", "content": content, "intents": [], "data_sources": []}

    # ── Analytics ──────────────────────────────────────────────────

    def _log_interaction(
        self,
        *,
        mode: str,
        message: str,
        sql: Optional[str],
        data_sources: List[str],
        response_text: str,
        duration_ms: int,
        usage: Optional[Dict] = None,
        demo_mode: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Escribe una entrada JSONL en backend/logs/chat_YYYY-MM-DD.jsonl."""
        unresolvable, signal = _detect_unresolvable(response_text) if response_text else (False, None)

        if not usage:
            resp_est = len(response_text) // 4 if response_text else 0
            usage = {
                "input_tokens": 0,
                "output_tokens": resp_est,
                "total_tokens": resp_est,
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
            "sql": sql or "",
            "response": response_text or "",
            "data_sources": data_sources,
            "tokens": usage,
            "duration_ms": duration_ms,
            "unresolvable": unresolvable,
        }

        if unresolvable:
            entry["unresolvable_signal"] = signal
            entry["NEEDS_REVIEW"] = True

        if error:
            entry["error"] = error
            entry["NEEDS_REVIEW"] = True

        _write_analytics(entry)

        flag = " ⚠️ NEEDS_REVIEW" if entry.get("NEEDS_REVIEW") else ""
        logger.info(
            f"[ANALYTICS]{flag} sql_tables={data_sources} tokens={usage.get('total_tokens', '?')} "
            f"({usage.get('source', '?')}) dur={duration_ms}ms | {message[:80]}"
        )


# ── Singleton ─────────────────────────────────────────────────────

_service_instance: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """
    Retorna la instancia singleton de ChatService.
    El provider de IA se inicializa una sola vez y se reutiliza en todas las requests.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ChatService()
    return _service_instance
