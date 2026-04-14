"""
Unit tests de servicios:
- csv_import: parse_*_df(), import_*_rows()
- analytics_service: AnalyticsService.calculate_stats(), detect_anomalies(), get_top_products()
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import (
    Venta, Gasto, Inventario, Cliente, Alerta, AlertConfig,
)
from app.auth.models import User, UserConfig
from app.auth.service import hash_password

TEST_UID = 1
from app.services.csv_import import (
    parse_ventas_df, import_ventas_rows,
    parse_gastos_df, import_gastos_rows,
    parse_inventario_df, import_inventario_rows,
    parse_clientes_df, import_clientes_rows,
)
from app.services.analytics_service import AnalyticsService


# ── Fixture DB aislada para unit tests ───────────────────────────────────────

@pytest.fixture(scope="module")
def unit_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def unit_db(unit_engine):
    Session = sessionmaker(bind=unit_engine)
    session = Session()
    # Crear usuario de test si no existe
    if not session.query(User).filter(User.id == TEST_UID).first():
        user = User(
            id=TEST_UID,
            email="unit@test.com",
            hashed_password=hash_password("testpass"),
            display_name="Unit User",
            is_active=True,
        )
        session.add(user)
        session.flush()
        session.add(UserConfig(user_id=TEST_UID))
        session.commit()
    # Sembrar AlertConfig con user_id
    rules = [
        "ventas_caida", "ventas_criticas", "ventas_tendencia",
        "gastos_pico", "gastos_excesivos", "gastos_tendencia",
        "inventario_bajo", "inventario_sin_stock",
    ]
    existing = {r.rule_id for r in session.query(AlertConfig).filter(AlertConfig.user_id == TEST_UID).all()}
    for r in rules:
        if r not in existing:
            session.add(AlertConfig(rule_id=r, enabled=True, user_id=TEST_UID))
    session.commit()
    yield session
    # Limpiar datos después de cada test
    for Model in [Venta, Gasto, Inventario, Cliente, Alerta]:
        session.query(Model).delete()
    session.query(AlertConfig).filter(AlertConfig.user_id == TEST_UID).delete()
    session.commit()
    session.close()


# ── parse_ventas_df ───────────────────────────────────────────────────────────

class TestParseVentasDf:
    def _df_valido(self):
        return pd.DataFrame([{
            "fecha": "2024-01-01",
            "producto_id": "P001",
            "nombre_producto": "Laptop",
            "cantidad": 2,
            "precio_unitario": 15000.0,
            "monto_total": 30000.0,
        }])

    def test_df_valido_pasa(self):
        df = self._df_valido()
        resultado = parse_ventas_df(df)
        assert len(resultado) == 1
        assert pd.api.types.is_datetime64_any_dtype(resultado["fecha"])
        assert resultado["cantidad"].dtype == int
        assert resultado["monto_total"].dtype == float

    def test_df_sin_columnas_requeridas_lanza_error(self):
        df = pd.DataFrame([{"fecha": "2024-01-01", "nombre_producto": "Laptop"}])
        with pytest.raises(ValueError, match="Columnas faltantes"):
            parse_ventas_df(df)

    def test_df_columnas_faltantes_especifica_cuales(self):
        df = pd.DataFrame([{"fecha": "2024-01-01"}])
        with pytest.raises(ValueError) as exc_info:
            parse_ventas_df(df)
        assert "producto_id" in str(exc_info.value)

    def test_df_convierte_tipos(self):
        df = pd.DataFrame([{
            "fecha": "2024-01-15",
            "producto_id": "P001",
            "nombre_producto": "Test",
            "cantidad": "3",
            "precio_unitario": "100.5",
            "monto_total": "301.5",
        }])
        resultado = parse_ventas_df(df)
        assert resultado["cantidad"].iloc[0] == 3
        assert resultado["precio_unitario"].iloc[0] == pytest.approx(100.5)


# ── import_ventas_rows ────────────────────────────────────────────────────────

class TestImportVentasRows:
    def test_importa_filas_correctamente(self, unit_db):
        df = pd.DataFrame([{
            "fecha": pd.Timestamp("2024-01-01"),
            "producto_id": "P001",
            "nombre_producto": "Laptop",
            "cantidad": 2,
            "precio_unitario": 15000.0,
            "monto_total": 30000.0,
            "categoria": "Electrónica",
        }])
        count, errores = import_ventas_rows(df, unit_db, user_id=TEST_UID)
        assert count == 1
        assert errores == []
        assert unit_db.query(Venta).count() == 1

    def test_importa_multiples_filas(self, unit_db):
        df = pd.DataFrame([
            {"fecha": pd.Timestamp("2024-01-01"), "producto_id": "P001",
             "nombre_producto": "A", "cantidad": 1, "precio_unitario": 100.0, "monto_total": 100.0},
            {"fecha": pd.Timestamp("2024-01-02"), "producto_id": "P002",
             "nombre_producto": "B", "cantidad": 2, "precio_unitario": 200.0, "monto_total": 400.0},
        ])
        count, errores = import_ventas_rows(df, unit_db, user_id=TEST_UID)
        assert count == 2
        assert errores == []


# ── parse_gastos_df ───────────────────────────────────────────────────────────

class TestParseGastosDf:
    def test_df_valido_pasa(self):
        df = pd.DataFrame([{
            "fecha": "2024-01-01",
            "descripcion": "Renta",
            "categoria": "servicios",
            "monto": 8000.0,
        }])
        resultado = parse_gastos_df(df)
        assert pd.api.types.is_datetime64_any_dtype(resultado["fecha"])
        assert resultado["monto"].dtype == float

    def test_df_sin_columnas_requeridas(self):
        df = pd.DataFrame([{"fecha": "2024-01-01", "descripcion": "Renta"}])
        with pytest.raises(ValueError, match="Columnas faltantes"):
            parse_gastos_df(df)


# ── parse_inventario_df ───────────────────────────────────────────────────────

class TestParseInventarioDf:
    def test_df_valido_pasa(self):
        df = pd.DataFrame([{
            "producto_id": "P001",
            "nombre_producto": "Laptop",
            "cantidad_actual": 10,
        }])
        resultado = parse_inventario_df(df)
        assert resultado["cantidad_actual"].dtype == int

    def test_df_sin_columnas_requeridas(self):
        df = pd.DataFrame([{"nombre_producto": "Laptop"}])
        with pytest.raises(ValueError, match="Columnas faltantes"):
            parse_inventario_df(df)

    def test_cantidad_minima_rellena_nulos(self):
        df = pd.DataFrame([{
            "producto_id": "P001",
            "nombre_producto": "Test",
            "cantidad_actual": 5,
            "cantidad_minima": None,
        }])
        resultado = parse_inventario_df(df)
        assert resultado["cantidad_minima"].iloc[0] == 0


# ── parse_clientes_df ─────────────────────────────────────────────────────────

class TestParseClientesDf:
    def test_df_valido_pasa(self):
        df = pd.DataFrame([{
            "cliente_id": "C001",
            "nombre": "Ana",
            "fecha_registro": "2024-01-01",
        }])
        resultado = parse_clientes_df(df)
        assert pd.api.types.is_datetime64_any_dtype(resultado["fecha_registro"])

    def test_df_sin_columnas_requeridas(self):
        df = pd.DataFrame([{"nombre": "Ana"}])
        with pytest.raises(ValueError, match="Columnas faltantes"):
            parse_clientes_df(df)


# ── AnalyticsService.calculate_stats ─────────────────────────────────────────

class TestCalculateStats:
    def test_sin_ventas_retorna_ceros(self, unit_db):
        stats = AnalyticsService.calculate_stats(unit_db, user_id=TEST_UID)
        assert stats["total_ventas"] == 0.0
        assert stats["cantidad_transacciones"] == 0
        assert stats["producto_mas_vendido"] == "N/A"

    def test_con_ventas_calcula_correctamente(self, unit_db):
        unit_db.add(Venta(
            user_id=TEST_UID, fecha=datetime(2024, 1, 1),
            producto_id="P001", nombre_producto="Laptop",
            cantidad=2, precio_unitario=15000.0, monto_total=30000.0,
            categoria="Electrónica",
        ))
        unit_db.add(Venta(
            user_id=TEST_UID, fecha=datetime(2024, 1, 2),
            producto_id="P002", nombre_producto="Mouse",
            cantidad=5, precio_unitario=500.0, monto_total=2500.0,
            categoria="Accesorios",
        ))
        unit_db.commit()

        stats = AnalyticsService.calculate_stats(unit_db, user_id=TEST_UID)
        assert stats["total_ventas"] == pytest.approx(32500.0)
        assert stats["cantidad_transacciones"] == 2
        assert stats["ticket_promedio"] == pytest.approx(16250.0)
        assert stats["producto_mas_vendido"] in ["Laptop", "Mouse"]
        assert stats["categoria_principal"] in ["Electrónica", "Accesorios"]

    def test_producto_mas_vendido_es_el_mas_frecuente(self, unit_db):
        for _ in range(3):
            unit_db.add(Venta(
                user_id=TEST_UID, fecha=datetime(2024, 1, 1),
                producto_id="P001", nombre_producto="Laptop",
                cantidad=1, precio_unitario=100.0, monto_total=100.0,
            ))
        unit_db.add(Venta(
            user_id=TEST_UID, fecha=datetime(2024, 1, 1),
            producto_id="P002", nombre_producto="Mouse",
            cantidad=1, precio_unitario=50.0, monto_total=50.0,
        ))
        unit_db.commit()

        stats = AnalyticsService.calculate_stats(unit_db, user_id=TEST_UID)
        assert stats["producto_mas_vendido"] == "Laptop"


# ── AnalyticsService.get_top_products ────────────────────────────────────────

class TestGetTopProducts:
    def test_sin_ventas_retorna_lista_vacia(self, unit_db):
        result = AnalyticsService.get_top_products(unit_db, user_id=TEST_UID, limit=5)
        assert result == []

    def test_retorna_top_por_monto(self, unit_db):
        unit_db.add(Venta(
            user_id=TEST_UID, fecha=datetime(2024, 1, 1),
            producto_id="P001", nombre_producto="Cara",
            cantidad=1, precio_unitario=50000.0, monto_total=50000.0,
        ))
        unit_db.add(Venta(
            user_id=TEST_UID, fecha=datetime(2024, 1, 1),
            producto_id="P002", nombre_producto="Barata",
            cantidad=10, precio_unitario=100.0, monto_total=1000.0,
        ))
        unit_db.commit()

        result = AnalyticsService.get_top_products(unit_db, user_id=TEST_UID, limit=2)
        assert len(result) == 2
        assert result[0]["nombre"] == "Cara"
        assert result[0]["monto_total"] == pytest.approx(50000.0)

    def test_limit_respetado(self, unit_db):
        for i in range(10):
            unit_db.add(Venta(
                user_id=TEST_UID, fecha=datetime(2024, 1, 1),
                producto_id=f"P{i:03d}", nombre_producto=f"Producto {i}",
                cantidad=1, precio_unitario=float(i + 1) * 100,
                monto_total=float(i + 1) * 100,
            ))
        unit_db.commit()

        result = AnalyticsService.get_top_products(unit_db, user_id=TEST_UID, limit=3)
        assert len(result) == 3


# ── AnalyticsService.detect_anomalies ────────────────────────────────────────

class TestDetectAnomalies:
    def test_sin_datos_no_genera_alertas(self, unit_db):
        alertas = AnalyticsService.detect_anomalies(unit_db, user_id=TEST_UID)
        assert alertas == []

    def test_inventario_bajo_genera_alerta(self, unit_db):
        unit_db.add(Inventario(
            user_id=TEST_UID, producto_id="INV-001",
            nombre_producto="Stock Bajo",
            cantidad_actual=2,
            cantidad_minima=10,
        ))
        unit_db.commit()

        alertas = AnalyticsService.detect_anomalies(unit_db, user_id=TEST_UID)
        tipos = [a.tipo for a in alertas]
        assert "inventario" in tipos

    def test_inventario_sin_stock_genera_alerta_critica(self, unit_db):
        unit_db.add(Inventario(
            user_id=TEST_UID, producto_id="INV-002",
            nombre_producto="Sin Stock",
            cantidad_actual=0,
        ))
        unit_db.commit()

        alertas = AnalyticsService.detect_anomalies(unit_db, user_id=TEST_UID)
        criticas = [a for a in alertas if a.nivel == "critical" and a.tipo == "inventario"]
        assert len(criticas) > 0

    def test_no_duplica_alertas_del_mismo_dia(self, unit_db):
        unit_db.add(Inventario(
            user_id=TEST_UID, producto_id="INV-003",
            nombre_producto="Bajo",
            cantidad_actual=1,
            cantidad_minima=10,
        ))
        unit_db.commit()

        alertas1 = AnalyticsService.detect_anomalies(unit_db, user_id=TEST_UID)
        alertas2 = AnalyticsService.detect_anomalies(unit_db, user_id=TEST_UID)
        # Segunda llamada no debe duplicar alertas de hoy
        assert len(alertas2) == 0

    def test_regla_deshabilitada_no_genera_alerta(self, unit_db):
        # Deshabilitar inventario_sin_stock
        config = unit_db.query(AlertConfig).filter(
            AlertConfig.user_id == TEST_UID,
            AlertConfig.rule_id == "inventario_sin_stock",
        ).first()
        config.enabled = False
        unit_db.commit()

        unit_db.add(Inventario(
            user_id=TEST_UID, producto_id="INV-004",
            nombre_producto="Sin Stock",
            cantidad_actual=0,
        ))
        unit_db.commit()

        alertas = AnalyticsService.detect_anomalies(unit_db, user_id=TEST_UID)
        sin_stock = [a for a in alertas if a.rule_id == "inventario_sin_stock"]
        assert sin_stock == []

        # Restaurar
        config.enabled = True
        unit_db.commit()
