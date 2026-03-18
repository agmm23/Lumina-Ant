"""
Tests del router de clientes:
- POST /api/clientes/upload-csv  (con upsert por cliente_id)
- GET /api/clientes/
- POST /api/clientes/
- PATCH /api/clientes/{id}
- DELETE /api/clientes/{id}
"""

import io
import pytest
from datetime import datetime
from tests.conftest import make_cliente, CLIENTES_CSV


# ── CSV Upload (upsert) ───────────────────────────────────────────────────────

class TestClientesUpload:
    def test_upload_csv_valido(self, client):
        resp = client.post(
            "/api/clientes/upload-csv",
            files={"file": ("clientes.csv", io.BytesIO(CLIENTES_CSV.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["clientes_creados"] == 2

    def test_upload_upsert_actualiza_existente(self, client, db):
        # Primera carga
        client.post(
            "/api/clientes/upload-csv",
            files={"file": ("clientes.csv", io.BytesIO(CLIENTES_CSV.encode()), "text/csv")},
        )
        # Segunda carga con mismo cliente_id → debe actualizar
        csv_update = (
            "cliente_id,nombre,fecha_registro\n"
            "C001,Ana García Actualizada,2024-01-01\n"
        )
        resp = client.post(
            "/api/clientes/upload-csv",
            files={"file": ("clientes.csv", io.BytesIO(csv_update.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["clientes_actualizados"] == 1

    def test_upload_csv_sin_columnas_requeridas(self, client):
        csv_malo = "nombre,email\nAna,ana@mail.com\n"
        resp = client.post(
            "/api/clientes/upload-csv",
            files={"file": ("clientes.csv", io.BytesIO(csv_malo.encode()), "text/csv")},
        )
        assert resp.status_code == 400

    def test_upload_con_column_mapping(self, client):
        csv = "id,full_name,reg_date\nC001,Juan Pérez,2024-01-01\n"
        import json
        mapping = json.dumps({
            "id": "cliente_id",
            "full_name": "nombre",
            "reg_date": "fecha_registro",
        })
        resp = client.post(
            "/api/clientes/upload-csv",
            files={"file": ("clientes.csv", io.BytesIO(csv.encode()), "text/csv")},
            data={"column_mapping": mapping},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["clientes_creados"] == 1


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestClientesCRUD:
    def test_listar_clientes_vacio(self, client):
        # solo_activos=False para ver todos, activos=False → 0
        resp = client.get("/api/clientes/?solo_activos=false")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_crear_cliente(self, client):
        payload = {
            "cliente_id": "C001",
            "nombre": "María García",
            "email": "maria@mail.com",
            "telefono": "5551234567",
            "ciudad": "CDMX",
            "fecha_registro": "2024-01-01T00:00:00",
            "activo": True,
        }
        resp = client.post("/api/clientes/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["nombre"] == "María García"
        assert data["cliente_id"] == "C001"
        assert "id" in data

    def test_crear_cliente_sin_nombre(self, client):
        payload = {
            "cliente_id": "C001",
            "fecha_registro": "2024-01-01T00:00:00",
        }
        resp = client.post("/api/clientes/", json=payload)
        assert resp.status_code == 422

    def test_crear_cliente_duplicado(self, client, db):
        make_cliente(db, cliente_id="C001")
        resp = client.post("/api/clientes/", json={
            "cliente_id": "C001",
            "nombre": "Duplicado",
            "fecha_registro": "2024-01-01T00:00:00",
        })
        assert resp.status_code == 400

    def test_listar_clientes_con_datos(self, client, db):
        make_cliente(db, cliente_id="C001")
        make_cliente(db, cliente_id="C002", nombre="Pedro López")

        # Por defecto solo_activos=True, ambos son activos
        resp = client.get("/api/clientes/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_editar_cliente_patch(self, client, db):
        c = make_cliente(db)
        resp = client.patch(f"/api/clientes/{c.id}", json={
            "nombre": "Nombre Actualizado",
            "email": "nuevo@mail.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["nombre"] == "Nombre Actualizado"

    def test_editar_cliente_inexistente(self, client):
        resp = client.patch("/api/clientes/99999", json={"nombre": "X"})
        assert resp.status_code == 404

    def test_eliminar_cliente(self, client, db):
        c = make_cliente(db)
        resp = client.delete(f"/api/clientes/{c.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_eliminar_cliente_inexistente(self, client):
        resp = client.delete("/api/clientes/99999")
        assert resp.status_code == 404

    def test_cliente_campos_respuesta(self, client, db):
        make_cliente(db)
        resp = client.get("/api/clientes/")
        c = resp.json()[0]
        for campo in ["id", "cliente_id", "nombre", "fecha_registro", "activo"]:
            assert campo in c

    def test_desactivar_cliente(self, client, db):
        c = make_cliente(db)
        resp = client.patch(f"/api/clientes/{c.id}/desactivar")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"


# ── Filtros ────────────────────────────────────────────────────────────────────

class TestClientesFiltros:
    def test_solo_activos_por_defecto(self, client, db):
        make_cliente(db, cliente_id="C001", activo=True)
        make_cliente(db, cliente_id="C002", nombre="Inactivo", activo=False)

        # Por defecto solo_activos=True
        resp = client.get("/api/clientes/")
        activos = resp.json()
        assert all(c["activo"] for c in activos)
        assert len(activos) == 1

    def test_listar_todos_incluye_inactivos(self, client, db):
        make_cliente(db, cliente_id="C001", activo=True)
        make_cliente(db, cliente_id="C002", nombre="Inactivo", activo=False)

        resp = client.get("/api/clientes/?solo_activos=false")
        assert len(resp.json()) == 2
