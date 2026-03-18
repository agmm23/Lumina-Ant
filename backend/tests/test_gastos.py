"""
Tests del router de gastos:
- POST /api/gastos/upload-csv
- GET /api/gastos/
- POST /api/gastos/
- DELETE /api/gastos/{id}
- GET /api/gastos/analytics/resumen
"""

import io
import pytest
from datetime import datetime
from tests.conftest import make_gasto, GASTOS_CSV


# ── CSV Upload ────────────────────────────────────────────────────────────────

class TestGastosUpload:
    def test_upload_csv_valido(self, client):
        resp = client.post(
            "/api/gastos/upload-csv",
            files={"file": ("gastos.csv", io.BytesIO(GASTOS_CSV.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["gastos_creados"] == 3

    def test_upload_csv_sin_columnas_requeridas(self, client):
        csv_malo = "fecha,descripcion\n2024-01-01,Renta\n"
        resp = client.post(
            "/api/gastos/upload-csv",
            files={"file": ("gastos.csv", io.BytesIO(csv_malo.encode()), "text/csv")},
        )
        assert resp.status_code == 400

    def test_upload_reemplaza_datos_anteriores(self, client, db):
        make_gasto(db)
        resp = client.post(
            "/api/gastos/upload-csv",
            files={"file": ("gastos.csv", io.BytesIO(GASTOS_CSV.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["gastos_creados"] == 3

    def test_upload_con_column_mapping(self, client):
        csv = "date,desc,cat,amount\n2024-01-01,Renta,servicios,8000\n"
        import json
        mapping = json.dumps({
            "date": "fecha",
            "desc": "descripcion",
            "cat": "categoria",
            "amount": "monto",
        })
        resp = client.post(
            "/api/gastos/upload-csv",
            files={"file": ("gastos.csv", io.BytesIO(csv.encode()), "text/csv")},
            data={"column_mapping": mapping},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["gastos_creados"] == 1


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestGastosCRUD:
    def test_listar_gastos_vacio(self, client):
        resp = client.get("/api/gastos/?limit=0")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_crear_gasto(self, client):
        payload = {
            "fecha": "2024-01-15T10:00:00",
            "descripcion": "Pago de luz",
            "categoria": "servicios",
            "monto": 1500.0,
            "nombre_proveedor": "CFE",
        }
        resp = client.post("/api/gastos/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["descripcion"] == "Pago de luz"
        assert data["monto"] == 1500.0
        assert "id" in data

    def test_crear_gasto_monto_invalido(self, client):
        payload = {
            "fecha": "2024-01-15T10:00:00",
            "descripcion": "Gasto",
            "categoria": "servicios",
            "monto": 0.0,  # inválido: debe ser > 0
        }
        resp = client.post("/api/gastos/", json=payload)
        assert resp.status_code == 422

    def test_listar_gastos_con_datos(self, client, db):
        make_gasto(db, descripcion="Renta")
        make_gasto(db, descripcion="Electricidad")

        resp = client.get("/api/gastos/?limit=0")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_eliminar_gasto(self, client, db):
        g = make_gasto(db)
        resp = client.delete(f"/api/gastos/{g.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

        resp = client.get("/api/gastos/?limit=0")
        assert g.id not in [x["id"] for x in resp.json()]

    def test_eliminar_gasto_inexistente(self, client):
        resp = client.delete("/api/gastos/99999")
        assert resp.status_code == 404

    def test_gasto_campos_respuesta(self, client, db):
        make_gasto(db)
        resp = client.get("/api/gastos/?limit=0")
        gasto = resp.json()[0]
        for campo in ["id", "fecha", "descripcion", "categoria", "monto"]:
            assert campo in gasto

    def test_get_gasto_por_id(self, client, db):
        g = make_gasto(db)
        resp = client.get(f"/api/gastos/{g.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == g.id


# ── Analytics de gastos ───────────────────────────────────────────────────────

class TestGastosAnalytics:
    def test_analytics_sin_datos(self, client):
        resp = client.get("/api/gastos/analytics/resumen")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_gastos"] == 0.0
        assert data["num_registros"] == 0

    def test_analytics_con_datos(self, client, db):
        make_gasto(db, monto=8000.0, categoria="servicios")
        make_gasto(db, monto=1200.0, categoria="insumos")

        resp = client.get("/api/gastos/analytics/resumen")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_gastos"] == pytest.approx(9200.0)
        assert data["num_registros"] == 2
        assert "por_categoria" in data
        assert "serie_temporal" in data

    def test_analytics_por_categoria(self, client, db):
        make_gasto(db, monto=5000.0, categoria="servicios")
        make_gasto(db, monto=3000.0, categoria="servicios")
        make_gasto(db, monto=1000.0, categoria="insumos")

        resp = client.get("/api/gastos/analytics/resumen")
        data = resp.json()
        cats = {c["categoria"]: c["total"] for c in data["por_categoria"]}
        assert cats["servicios"] == pytest.approx(8000.0)
        assert cats["insumos"] == pytest.approx(1000.0)

    def test_analytics_campos_requeridos(self, client):
        resp = client.get("/api/gastos/analytics/resumen")
        data = resp.json()
        campos = ["total_gastos", "num_registros", "gasto_promedio",
                  "top_categoria", "serie_temporal", "por_categoria"]
        for campo in campos:
            assert campo in data
