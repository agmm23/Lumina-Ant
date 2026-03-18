"""
Tests del router de inventarios:
- POST /api/inventarios/upload-csv  (con upsert por producto_id)
- GET /api/inventarios/
- POST /api/inventarios/
- PATCH /api/inventarios/{id}
- DELETE /api/inventarios/{id}
- GET /api/inventarios/analytics/resumen
"""

import io
import pytest
from tests.conftest import make_inventario, INVENTARIO_CSV


# ── CSV Upload (upsert) ───────────────────────────────────────────────────────

class TestInventariosUpload:
    def test_upload_csv_valido(self, client):
        resp = client.post(
            "/api/inventarios/upload-csv",
            files={"file": ("inventario.csv", io.BytesIO(INVENTARIO_CSV.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["items_creados"] == 3

    def test_upload_upsert_actualiza_existente(self, client, db):
        # Primera carga
        client.post(
            "/api/inventarios/upload-csv",
            files={"file": ("inventario.csv", io.BytesIO(INVENTARIO_CSV.encode()), "text/csv")},
        )
        # Segunda carga con mismo producto_id → debe actualizar
        csv_update = (
            "producto_id,nombre_producto,cantidad_actual,precio_venta\n"
            "P001,Laptop Updated,99,20000\n"
        )
        resp = client.post(
            "/api/inventarios/upload-csv",
            files={"file": ("inventario.csv", io.BytesIO(csv_update.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items_actualizados"] == 1

    def test_upload_csv_sin_columnas_requeridas(self, client):
        csv_malo = "nombre,precio\nLaptop,15000\n"
        resp = client.post(
            "/api/inventarios/upload-csv",
            files={"file": ("inventario.csv", io.BytesIO(csv_malo.encode()), "text/csv")},
        )
        assert resp.status_code == 400

    def test_upload_con_column_mapping(self, client):
        csv = "id_prod,name,stock\nP001,Laptop,10\n"
        import json
        mapping = json.dumps({
            "id_prod": "producto_id",
            "name": "nombre_producto",
            "stock": "cantidad_actual",
        })
        resp = client.post(
            "/api/inventarios/upload-csv",
            files={"file": ("inventario.csv", io.BytesIO(csv.encode()), "text/csv")},
            data={"column_mapping": mapping},
        )
        assert resp.status_code == 200


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestInventariosCRUD:
    def test_listar_inventario_vacio(self, client):
        resp = client.get("/api/inventarios/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_crear_inventario(self, client):
        payload = {
            "producto_id": "P001",
            "nombre_producto": "Laptop",
            "cantidad_actual": 20,
            "cantidad_minima": 5,
            "precio_compra": 12000.0,
            "precio_venta": 15000.0,
            "categoria": "Electrónica",
        }
        resp = client.post("/api/inventarios/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["producto_id"] == "P001"
        assert data["cantidad_actual"] == 20
        assert "id" in data

    def test_crear_inventario_duplicado(self, client, db):
        make_inventario(db, producto_id="P001")
        resp = client.post("/api/inventarios/", json={
            "producto_id": "P001",
            "nombre_producto": "Otro",
            "cantidad_actual": 5,
        })
        assert resp.status_code == 400

    def test_crear_inventario_cantidad_negativa(self, client):
        payload = {
            "producto_id": "P001",
            "nombre_producto": "Laptop",
            "cantidad_actual": -1,  # inválido
        }
        resp = client.post("/api/inventarios/", json=payload)
        assert resp.status_code == 422

    def test_listar_inventario_con_datos(self, client, db):
        make_inventario(db, producto_id="P001")
        make_inventario(db, producto_id="P002", nombre_producto="Mouse")

        resp = client.get("/api/inventarios/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_editar_inventario_patch(self, client, db):
        inv = make_inventario(db)
        resp = client.patch(f"/api/inventarios/{inv.id}", json={
            "cantidad_actual": 100,
            "precio_venta": 200.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cantidad_actual"] == 100

    def test_editar_inventario_inexistente(self, client):
        resp = client.patch("/api/inventarios/99999", json={"cantidad_actual": 10})
        assert resp.status_code == 404

    def test_eliminar_inventario(self, client, db):
        inv = make_inventario(db)
        resp = client.delete(f"/api/inventarios/{inv.id}")
        assert resp.status_code == 200
        assert inv.id not in [i["id"] for i in client.get("/api/inventarios/").json()]

    def test_eliminar_inventario_inexistente(self, client):
        resp = client.delete("/api/inventarios/99999")
        assert resp.status_code == 404

    def test_inventario_campos_respuesta(self, client, db):
        make_inventario(db)
        resp = client.get("/api/inventarios/")
        item = resp.json()[0]
        for campo in ["id", "producto_id", "nombre_producto", "cantidad_actual"]:
            assert campo in item

    def test_get_inventario_por_id(self, client, db):
        inv = make_inventario(db)
        resp = client.get(f"/api/inventarios/{inv.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == inv.id


# ── Analytics de inventario ───────────────────────────────────────────────────

class TestInventarioAnalytics:
    def test_analytics_resumen_sin_datos(self, client):
        resp = client.get("/api/inventarios/analytics/resumen")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_productos"] == 0
        assert data["bajos_stock"] == 0

    def test_analytics_resumen_con_datos(self, client, db):
        make_inventario(db, producto_id="P001", cantidad_actual=10,
                        cantidad_minima=5, precio_venta=100.0, precio_compra=60.0)
        make_inventario(db, producto_id="P002", nombre_producto="Low",
                        cantidad_actual=2, cantidad_minima=10)

        resp = client.get("/api/inventarios/analytics/resumen")
        data = resp.json()
        assert data["total_productos"] == 2
        assert data["bajos_stock"] == 1


# ── Stock bajo ────────────────────────────────────────────────────────────────

class TestInventarioStockBajo:
    def test_productos_sin_stock(self, client, db):
        make_inventario(db, producto_id="P001", cantidad_actual=0)
        make_inventario(db, producto_id="P002", cantidad_actual=10)

        resp = client.get("/api/inventarios/")
        sin_stock = [p for p in resp.json() if p["cantidad_actual"] == 0]
        assert len(sin_stock) == 1

    def test_stats_bajo_stock(self, client, db):
        make_inventario(db, producto_id="P001", cantidad_actual=2, cantidad_minima=10)
        make_inventario(db, producto_id="P002", cantidad_actual=15, cantidad_minima=10)

        resp = client.get("/api/inventarios/stats/bajo-stock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cantidad_items"] == 1
