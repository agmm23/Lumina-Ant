"""
Guardia arquitectónico: DB_SCHEMA del copiloto IA vs. tablas reales.

Este test falla intencionalmente si se agrega una tabla nueva a la base de datos
sin haber decidido explícitamente si incluirla o no en el esquema enviado a la IA.

── Qué hacer cuando este test falla ────────────────────────────────────────────
Si agregaste un nuevo modelo SQLAlchemy y el test te bloquea, debes tomar una
decisión consciente y registrarla en una de las dos listas de abajo:

  TABLAS_EN_SCHEMA   → tablas útiles para consultas de negocio (el copiloto las conoce)
  TABLAS_EXCLUIDAS   → tablas de infraestructura / configuración (el copiloto NO las conoce)

Criterios para incluir una tabla en el schema:
  ✅ Contiene datos de negocio que el usuario puede querer consultar en lenguaje natural
  ✅ Sus columnas son comprensibles para el modelo de IA (sin JSON serializados opacos)
  ❌ Es una tabla de configuración o de infraestructura interna
  ❌ Tiene columnas con datos sensibles (tokens, hashed_passwords, etc.)
  ❌ Sus datos ya se exponen a través de otra tabla o endpoint
────────────────────────────────────────────────────────────────────────────────
"""

import re
import pytest
from app.database import Base

# Importar todos los modelos para que queden registrados en Base.metadata
from app.models.models import (  # noqa: F401
    Venta, Gasto, Inventario, Cliente, Alerta,
    WatchedFile, AlertConfig, ColumnMapping, Prediccion,
)
from app.auth.models import User, UserConfig  # noqa: F401

# ── Decisiones explícitas sobre cada tabla ───────────────────────────────────

# Tablas incluidas en DB_SCHEMA (chat_service.py) — el copiloto las conoce
TABLAS_EN_SCHEMA: set[str] = {
    "ventas",
    "gastos",
    "inventario",
    "clientes",
}

# Tablas excluidas a propósito — el copiloto NO las conoce
# Motivo resumido junto a cada una para que quede el razonamiento
TABLAS_EXCLUIDAS: set[str] = {
    "alertas",          # edge case; la UI ya las muestra; columna `detalles` es JSON opaco
    "watched_files",    # infraestructura del watcher; sin valor para consultas de negocio
    "alert_configs",    # configuración interna de reglas; no es dato de negocio
    "column_mappings",  # metadatos de importación; sin valor para el copiloto
    "users",            # datos sensibles (hashed_password, tokens)
    "user_configs",     # preferencias de UI; sin valor para consultas de negocio
    "predicciones",     # modelo incompleto (sin router ni endpoints); sin user_id → pendiente de implementar
}

# ── Test ──────────────────────────────────────────────────────────────────────

def test_todas_las_tablas_tienen_decision_explicita():
    """
    Verifica que cada tabla de la BD esté en TABLAS_EN_SCHEMA o en TABLAS_EXCLUIDAS.
    Si falla: agrega la nueva tabla a una de las dos listas con su justificación.
    """
    tablas_reales = set(Base.metadata.tables.keys())
    tablas_evaluadas = TABLAS_EN_SCHEMA | TABLAS_EXCLUIDAS
    sin_decision = tablas_reales - tablas_evaluadas

    assert not sin_decision, (
        f"\n\n⚠️  ACCIÓN REQUERIDA — Tablas nuevas sin decisión de schema IA:\n"
        f"   {sorted(sin_decision)}\n\n"
        f"Agrega cada tabla a TABLAS_EN_SCHEMA o TABLAS_EXCLUIDAS\n"
        f"en backend/tests/test_chat_schema.py con su justificación.\n"
        f"Ver criterios en el docstring del módulo."
    )


def test_tablas_en_schema_existen_en_bd():
    """
    Verifica que las tablas declaradas en TABLAS_EN_SCHEMA sigan existiendo en la BD.
    Si falla: una tabla fue renombrada o eliminada — actualiza TABLAS_EN_SCHEMA y DB_SCHEMA.
    """
    tablas_reales = set(Base.metadata.tables.keys())
    eliminadas = TABLAS_EN_SCHEMA - tablas_reales

    assert not eliminadas, (
        f"\n\n⚠️  Tablas en TABLAS_EN_SCHEMA que ya no existen en la BD:\n"
        f"   {sorted(eliminadas)}\n\n"
        f"Actualiza TABLAS_EN_SCHEMA en test_chat_schema.py y\n"
        f"elimina su bloque de DB_SCHEMA en chat_service.py."
    )


def test_db_schema_cubre_exactamente_tablas_en_schema():
    """
    Verifica que el DB_SCHEMA en chat_service.py mencione exactamente
    las tablas de TABLAS_EN_SCHEMA (ni más ni menos).
    Si falla: sincroniza DB_SCHEMA con TABLAS_EN_SCHEMA.
    """
    from app.services.chat_service import DB_SCHEMA

    # Extrae los nombres de tabla del bloque "TABLA: <nombre>"
    tablas_en_prompt = set(re.findall(r"TABLA:\s+(\w+)", DB_SCHEMA))

    faltantes = TABLAS_EN_SCHEMA - tablas_en_prompt
    sobrantes = tablas_en_prompt - TABLAS_EN_SCHEMA

    assert not faltantes and not sobrantes, (
        f"\n\n⚠️  DB_SCHEMA en chat_service.py no coincide con TABLAS_EN_SCHEMA:\n"
        + (f"   Faltan en DB_SCHEMA: {sorted(faltantes)}\n" if faltantes else "")
        + (f"   Sobran en DB_SCHEMA (no están en TABLAS_EN_SCHEMA): {sorted(sobrantes)}\n" if sobrantes else "")
        + f"\nSincroniza DB_SCHEMA (chat_service.py) con TABLAS_EN_SCHEMA (test_chat_schema.py)."
    )
