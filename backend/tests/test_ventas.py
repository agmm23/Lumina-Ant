"""
Tests del router de ventas:
- POST /api/ventas/upload-csv
- GET /api/ventas/
- DELETE /api/ventas/{id}
- GET /api/ventas/analytics/resumen
"""

import io
import pytest
from datetime import datetime
from tests.conftest import make_venta, VENTAS_CSV


# ── CSV Upload ────────────────────────────────────────────────────────────────

class TestVentasUpload:
    def test_upload_csv_valido(self, client):
        resp = client.post(
            "/api/ventas/upload-csv",
            files={"file": ("ventas.csv", io.BytesIO(VENTAS_CSV.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["ventas_creadas"] == 3

    def test_upload_csv_sin_columnas_requeridas(self, client):
        csv_malo = "fecha,producto\n2024-01-01,Laptop\n"
        resp = client.post(
            "/api/ventas/upload-csv",
            files={"file": ("ventas.csv", io.BytesIO(csv_malo.encode()), "text/csv")},
        )
        assert resp.status_code == 400

    def test_upload_csv_con_column_mapping(self, client):
        csv = (
            "date,prod_id,prod_name,qty,unit_price,amount,cat\n"
            "2024-01-01,P001,Laptop,1,15000,15000,Electrónica\n"
        )
        import json
        mapping = json.dumps({
            "date": "fecha",
            "prod_id": "producto_id",
            "prod_name": "nombre_producto",
            "qty": "cantidad",
            "unit_price": "precio_unitario",
            "amount": "monto_total",
            "cat": "categoria",
        })
        resp = client.post(
            "/api/ventas/upload-csv",
            files={"file": ("ventas.csv", io.BytesIO(csv.encode()), "text/csv")},
            data={"column_mapping": mapping},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["ventas_creadas"] == 1

    def test_upload_reemplaza_datos_anteriores(self, client, db):
        make_venta(db)
        resp = client.post(
            "/api/ventas/upload-csv",
            files={"file": ("ventas.csv", io.BytesIO(VENTAS_CSV.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["ventas_creadas"] == 3

    def test_upload_csv_vacio_importa_cero(self, client):
        csv_vacio = "fecha,producto_id,nombre_producto,cantidad,precio_unitario,monto_total\n"
        resp = client.post(
            "/api/ventas/upload-csv",
            files={"file": ("ventas.csv", io.BytesIO(csv_vacio.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["ventas_creadas"] == 0

    def test_upload_retorna_errores_en_data(self, client):
        resp = client.post(
            "/api/ventas/upload-csv",
            files={"file": ("ventas.csv", io.BytesIO(VENTAS_CSV.encode()), "text/csv")},
        )
        assert "errores" in resp.json()["data"]


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestVentasCRUD:
    def test_listar_ventas_vacia(self, client):
        # limit=0 devuelve todos
        resp = client.get("/api/ventas/?limit=0")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_listar_ventas_con_datos(self, client, db):
        make_venta(db, nombre_producto="Laptop")
        make_venta(db, producto_id="P002", nombre_producto="Mouse")

        resp = client.get("/api/ventas/?limit=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_listar_ventas_paginacion(self, client, db):
        for i in range(5):
            make_venta(db, producto_id=f"P{i:03d}", nombre_producto=f"Prod {i}")

        # Por defecto limit=15, skip=0
        resp = client.get("/api/ventas/?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_eliminar_venta(self, client, db):
        v = make_venta(db)
        resp = client.delete(f"/api/ventas/{v.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

        # Verificar que ya no existe
        resp = client.get("/api/ventas/?limit=0")
        assert all(venta["id"] != v.id for venta in resp.json())

    def test_eliminar_venta_inexistente(self, client):
        resp = client.delete("/api/ventas/99999")
        assert resp.status_code == 404

    def test_venta_campos_respuesta(self, client, db):
        make_venta(db)
        resp = client.get("/api/ventas/?limit=0")
        venta = resp.json()[0]
        campos = ["id", "fecha", "producto_id", "nombre_producto",
                  "cantidad", "precio_unitario", "monto_total"]
        for campo in campos:
            assert campo in venta

    def test_filtro_fecha_from(self, client, db):
        make_venta(db, fecha=datetime(2024, 1, 1))
        make_venta(db, producto_id="P002", nombre_producto="Nuevo",
                   fecha=datetime(2024, 6, 1))

        resp = client.get("/api/ventas/?date_from=2024-06-01&limit=0")
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["nombre_producto"] == "Nuevo" for v in data)


# ── Analytics de ventas ───────────────────────────────────────────────────────

class TestVentasAnalytics:
    def test_analytics_sin_datos(self, client):
        resp = client.get("/api/ventas/analytics/resumen")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ventas"] == 0.0
        assert data["num_transacciones"] == 0

    def test_analytics_con_datos(self, client, db):
        make_venta(db, monto_total=1000.0, cantidad=2, categoria="A")
        make_venta(db, producto_id="P002", nombre_producto="Otro", monto_total=500.0, cantidad=1, categoria="B")

        resp = client.get("/api/ventas/analytics/resumen")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_ventas"] == pytest.approx(1500.0)
        assert data["num_transacciones"] == 2
        assert "serie_temporal" in data
        assert "por_categoria" in data
        assert "top_productos" in data

    def test_analytics_serie_temporal(self, client, db):
        make_venta(db, fecha=datetime(2024, 1, 1))
        make_venta(db, producto_id="P002", nombre_producto="Otro",
                   fecha=datetime(2024, 1, 2), monto_total=300.0, cantidad=1)

        resp = client.get("/api/ventas/analytics/resumen")
        data = resp.json()
        serie = data["serie_temporal"]
        assert isinstance(serie, list)
        assert len(serie) >= 1
        assert "fecha" in serie[0]
        assert "total" in serie[0]

    def test_analytics_por_categoria(self, client, db):
        make_venta(db, monto_total=5000.0, categoria="Electrónica")
        make_venta(db, producto_id="P002", nombre_producto="Silla",
                   monto_total=1000.0, categoria="Muebles")

        resp = client.get("/api/ventas/analytics/resumen")
        data = resp.json()
        cats = {c["categoria"]: c["total"] for c in data["por_categoria"]}
        assert "Electrónica" in cats

    def test_analytics_group_by_mes(self, client, db):
        make_venta(db, fecha=datetime(2024, 1, 15))
        make_venta(db, producto_id="P002", nombre_producto="Otro",
                   fecha=datetime(2024, 2, 10), monto_total=300.0, cantidad=1)

        resp = client.get("/api/ventas/analytics/resumen?group_by=mes")
        assert resp.status_code == 200
