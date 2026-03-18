"""
Configuración global de tests para Lumina Ant.
Usa SQLite en memoria para aislamiento completo.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from app.database import Base, get_db
from app.models.models import AlertConfig, Venta, Gasto, Inventario, Cliente
from datetime import datetime

# ── Motor SQLite en memoria ──────────────────────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear tablas una sola vez para toda la sesión de tests
Base.metadata.create_all(bind=engine)

ALERT_RULES = [
    "ventas_caida", "ventas_criticas", "ventas_tendencia",
    "gastos_pico", "gastos_excesivos", "gastos_tendencia",
    "inventario_bajo", "inventario_sin_stock",
]


def _seed_alert_configs(db):
    """Siembra las reglas de alerta en la DB de test."""
    existing = {r.rule_id for r in db.query(AlertConfig).all()}
    for rule_id in ALERT_RULES:
        if rule_id not in existing:
            db.add(AlertConfig(rule_id=rule_id, enabled=True))
    db.commit()


def _clear_tables(db):
    """Limpia todos los datos entre tests, manteniendo AlertConfig."""
    for Model in [Venta, Gasto, Inventario, Cliente]:
        db.query(Model).delete()
    from app.models.models import Alerta, WatchedFile, ColumnMapping
    db.query(Alerta).delete()
    db.query(WatchedFile).delete()
    db.query(ColumnMapping).delete()
    db.commit()


@pytest.fixture()
def db():
    """Sesión de base de datos limpia para cada test."""
    session = TestingSessionLocal()
    _seed_alert_configs(session)
    try:
        yield session
    finally:
        _clear_tables(session)
        session.close()


@pytest.fixture()
def client(db):
    """
    TestClient con DB en memoria inyectada.
    Mockea el watcher y el seed de producción para no tocar la DB real.
    """
    def override_get_db():
        yield db

    # Importar app aquí para evitar ejecución prematura de create_all real
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db

    # Mockear watcher_loop y _seed_alert_configs del main para no contaminar DB real
    with patch("app.main.watcher_loop", new_callable=AsyncMock), \
         patch("app.main._seed_alert_configs"), \
         patch("app.main._migrate_db"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.clear()


# ── Factories de datos de prueba ─────────────────────────────────────────────

def make_venta(db, **kwargs) -> Venta:
    defaults = dict(
        fecha=datetime(2024, 1, 15, 10, 0, 0),
        producto_id="PROD-001",
        nombre_producto="Producto Test",
        cantidad=5,
        precio_unitario=100.0,
        monto_total=500.0,
        categoria="Electrónica",
    )
    defaults.update(kwargs)
    v = Venta(**defaults)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def make_gasto(db, **kwargs) -> Gasto:
    defaults = dict(
        fecha=datetime(2024, 1, 15, 10, 0, 0),
        descripcion="Gasto de prueba",
        categoria="servicios",
        monto=200.0,
    )
    defaults.update(kwargs)
    g = Gasto(**defaults)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def make_inventario(db, **kwargs) -> Inventario:
    defaults = dict(
        producto_id="INV-001",
        nombre_producto="Inventario Test",
        cantidad_actual=50,
        cantidad_minima=10,
        precio_compra=80.0,
        precio_venta=120.0,
    )
    defaults.update(kwargs)
    i = Inventario(**defaults)
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def make_cliente(db, **kwargs) -> Cliente:
    defaults = dict(
        cliente_id="CLI-001",
        nombre="Cliente Test",
        email="test@ejemplo.com",
        fecha_registro=datetime(2024, 1, 1),
        activo=True,
    )
    defaults.update(kwargs)
    c = Cliente(**defaults)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ── CSV helpers ───────────────────────────────────────────────────────────────

VENTAS_CSV = (
    "fecha,producto_id,nombre_producto,cantidad,precio_unitario,monto_total,categoria\n"
    "2024-01-01,P001,Laptop,2,15000,30000,Electrónica\n"
    "2024-01-02,P002,Mouse,5,500,2500,Accesorios\n"
    "2024-01-03,P001,Laptop,1,15000,15000,Electrónica\n"
)

GASTOS_CSV = (
    "fecha,descripcion,categoria,monto,nombre_proveedor\n"
    "2024-01-01,Renta oficina,servicios,8000,Inmobiliaria XYZ\n"
    "2024-01-02,Luz y agua,servicios,1200,CFE\n"
    "2024-01-03,Papelería,insumos,350,Officemax\n"
)

INVENTARIO_CSV = (
    "producto_id,nombre_producto,cantidad_actual,cantidad_minima,precio_compra,precio_venta\n"
    "P001,Laptop,10,3,12000,15000\n"
    "P002,Mouse,50,10,300,500\n"
    "P003,Teclado,30,5,600,900\n"
)

CLIENTES_CSV = (
    "cliente_id,nombre,email,telefono,ciudad,fecha_registro\n"
    "C001,Ana García,ana@mail.com,5551234567,CDMX,2024-01-01\n"
    "C002,Juan López,juan@mail.com,5559876543,Monterrey,2024-01-15\n"
)
