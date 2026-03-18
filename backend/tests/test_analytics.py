"""
Tests del router de analytics:
- GET /api/analytics/stats
- GET /api/analytics/alertas
- POST /api/analytics/detect-anomalies
- GET /api/analytics/top-productos
- GET /api/analytics/alert-config
- PATCH /api/analytics/alert-config/{rule_id}
- PATCH /api/analytics/alertas/{id}/marcar-leida
"""

import pytest
from datetime import datetime, timedelta
from tests.conftest import make_venta, make_gasto, make_inventario
from app.models.models import Alerta, AlertConfig


# ── /api/analytics/stats ─────────────────────────────────────────────────────

class TestStats:
    def test_stats_sin_datos_retorna_ceros(self, client):
        resp = client.get("/api/analytics/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ventas"] == 0.0
        assert data["cantidad_transacciones"] == 0
        assert data["ticket_promedio"] == 0.0
        assert data["producto_mas_vendido"] == "N/A"
        assert data["categoria_principal"] == "N/A"

    def test_stats_con_ventas(self, client, db):
        make_venta(db, nombre_producto="Laptop", monto_total=15000.0, cantidad=1, categoria="Electrónica")
        make_venta(db, producto_id="P002", nombre_producto="Mouse", monto_total=500.0, cantidad=2, categoria="Accesorios")
        make_venta(db, nombre_producto="Laptop", monto_total=15000.0, cantidad=1, categoria="Electrónica")

        resp = client.get("/api/analytics/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ventas"] == pytest.approx(30500.0)
        assert data["cantidad_transacciones"] == 3
        assert data["ticket_promedio"] == pytest.approx(30500.0 / 3, rel=1e-3)
        assert data["producto_mas_vendido"] == "Laptop"
        assert data["categoria_principal"] == "Electrónica"

    def test_stats_campos_requeridos(self, client):
        resp = client.get("/api/analytics/stats")
        data = resp.json()
        campos = ["total_ventas", "cantidad_transacciones", "ticket_promedio",
                  "producto_mas_vendido", "categoria_principal"]
        for campo in campos:
            assert campo in data, f"Falta campo: {campo}"


# ── /api/analytics/alertas ───────────────────────────────────────────────────

class TestAlertas:
    def _crear_alerta(self, db, tipo="ventas", nivel="warning", leida=False, rule_id="ventas_caida"):
        a = Alerta(
            tipo=tipo,
            nivel=nivel,
            rule_id=rule_id,
            mensaje="Alerta de prueba",
            detalles="Detalles de prueba",
            leida=leida,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        return a

    def test_alertas_vacias(self, client):
        resp = client.get("/api/analytics/alertas")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_alertas_no_leidas(self, client, db):
        a1 = self._crear_alerta(db, leida=False)
        a2 = self._crear_alerta(db, leida=True, rule_id="ventas_criticas")

        resp = client.get("/api/analytics/alertas?solo_no_leidas=true")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert a1.id in ids
        assert a2.id not in ids

    def test_alertas_todas(self, client, db):
        self._crear_alerta(db, leida=False)
        self._crear_alerta(db, leida=True, rule_id="ventas_criticas")

        resp = client.get("/api/analytics/alertas?solo_no_leidas=false")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_alertas_filtro_tipo(self, client, db):
        self._crear_alerta(db, tipo="ventas", rule_id="ventas_caida")
        self._crear_alerta(db, tipo="gastos", rule_id="gastos_pico")

        resp = client.get("/api/analytics/alertas?solo_no_leidas=false&tipo=ventas")
        assert resp.status_code == 200
        for a in resp.json():
            assert a["tipo"] == "ventas"

    def test_alertas_estructura(self, client, db):
        self._crear_alerta(db)
        resp = client.get("/api/analytics/alertas?solo_no_leidas=false")
        data = resp.json()
        assert len(data) > 0
        alerta = data[0]
        for campo in ["id", "tipo", "nivel", "mensaje", "leida", "fecha_creacion"]:
            assert campo in alerta, f"Falta campo: {campo}"

    def test_alertas_solo_reglas_habilitadas(self, client, db):
        # Deshabilitar una regla
        config = db.query(AlertConfig).filter(AlertConfig.rule_id == "ventas_caida").first()
        config.enabled = False
        db.commit()

        self._crear_alerta(db, rule_id="ventas_caida")
        self._crear_alerta(db, rule_id="gastos_pico")

        resp = client.get("/api/analytics/alertas?solo_no_leidas=false")
        rule_ids = [a.get("rule_id") for a in resp.json()]
        assert "ventas_caida" not in rule_ids


# ── PATCH /api/analytics/alertas/{id}/marcar-leida ──────────────────────────

class TestMarcarLeida:
    def test_marcar_alerta_leida(self, client, db):
        a = Alerta(tipo="ventas", nivel="warning", rule_id="ventas_caida",
                   mensaje="Test", leida=False)
        db.add(a)
        db.commit()
        db.refresh(a)

        resp = client.patch(f"/api/analytics/alertas/{a.id}/marcar-leida")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

        db.refresh(a)
        assert a.leida is True

    def test_marcar_alerta_inexistente(self, client):
        resp = client.patch("/api/analytics/alertas/99999/marcar-leida")
        assert resp.status_code == 404


# ── POST /api/analytics/detect-anomalies ─────────────────────────────────────

class TestDetectAnomalies:
    def test_detect_anomalies_sin_datos(self, client):
        resp = client.post("/api/analytics/detect-anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "alerta" in data["message"].lower() or "análisis" in data["message"].lower()

    def test_detect_anomalies_con_inventario_bajo(self, client, db):
        # Producto con stock bajo (actual <= mínimo)
        make_inventario(db, producto_id="INV-LOW", nombre_producto="Producto Bajo",
                        cantidad_actual=2, cantidad_minima=10)

        resp = client.post("/api/analytics/detect-anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["data"]["alertas"], list)

    def test_detect_anomalies_retorna_estructura(self, client):
        resp = client.post("/api/analytics/detect-anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "message" in data
        assert "data" in data


# ── GET /api/analytics/top-productos ─────────────────────────────────────────

class TestTopProductos:
    def test_top_productos_sin_ventas(self, client):
        resp = client.get("/api/analytics/top-productos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["productos"] == []
        assert data["cantidad"] == 0

    def test_top_productos_con_ventas(self, client, db):
        make_venta(db, producto_id="P001", nombre_producto="Laptop", monto_total=30000.0, cantidad=2)
        make_venta(db, producto_id="P002", nombre_producto="Mouse", monto_total=1000.0, cantidad=5)
        make_venta(db, producto_id="P001", nombre_producto="Laptop", monto_total=15000.0, cantidad=1)

        resp = client.get("/api/analytics/top-productos?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cantidad"] <= 2
        assert data["productos"][0]["nombre"] == "Laptop"  # mayor monto total

    def test_top_productos_estructura(self, client, db):
        make_venta(db)
        resp = client.get("/api/analytics/top-productos")
        data = resp.json()
        assert len(data["productos"]) > 0
        p = data["productos"][0]
        for campo in ["producto_id", "nombre", "cantidad_vendida", "monto_total"]:
            assert campo in p

    def test_top_productos_limit(self, client, db):
        for i in range(10):
            make_venta(db, producto_id=f"P{i:03d}", nombre_producto=f"Producto {i}",
                       monto_total=float(1000 + i * 100))
        resp = client.get("/api/analytics/top-productos?limit=3")
        data = resp.json()
        assert len(data["productos"]) <= 3


# ── GET /api/analytics/alert-config ─────────────────────────────────────────

class TestAlertConfig:
    def test_get_alert_config(self, client):
        resp = client.get("/api/analytics/alert-config")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 8  # 8 reglas definidas en RULE_META

    def test_alert_config_estructura(self, client):
        resp = client.get("/api/analytics/alert-config")
        data = resp.json()
        regla = data[0]
        for campo in ["rule_id", "enabled", "label", "description", "tipo", "nivel", "params"]:
            assert campo in regla

    def test_patch_alert_config_disable(self, client):
        resp = client.patch(
            "/api/analytics/alert-config/ventas_caida",
            json={"enabled": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["rule_id"] == "ventas_caida"

    def test_patch_alert_config_params(self, client):
        resp = client.patch(
            "/api/analytics/alert-config/ventas_caida",
            json={"enabled": True, "params": {"umbral": 50, "periodo": 7}}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["params"]["umbral"] == 50
        assert data["params"]["periodo"] == 7

    def test_patch_alert_config_regla_inexistente(self, client):
        resp = client.patch(
            "/api/analytics/alert-config/regla_fantasma",
            json={"enabled": False}
        )
        assert resp.status_code == 404
