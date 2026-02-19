"""
Lumina_Ant - Servicio de auto-mapeo de columnas CSV
Mapea columnas de un CSV del usuario a los campos esperados del sistema.
Pipeline: exact → normalized → saved → synonym → fuzzy
"""

import unicodedata
import re
from difflib import SequenceMatcher
from typing import Dict, List, Set


# Columnas destino por datasource (fuente de verdad única)
DATASOURCE_COLUMNS = {
    "ventas": [
        {"name": "fecha", "required": True, "hint": "YYYY-MM-DD o DD/MM/YYYY"},
        {"name": "producto_id", "required": True},
        {"name": "nombre_producto", "required": True},
        {"name": "cantidad", "required": True, "hint": "entero"},
        {"name": "precio_unitario", "required": True, "hint": "decimal"},
        {"name": "monto_total", "required": True, "hint": "decimal"},
        {"name": "cliente_id", "required": False},
        {"name": "categoria", "required": False},
    ],
    "gastos": [
        {"name": "fecha", "required": True, "hint": "YYYY-MM-DD o DD/MM/YYYY"},
        {"name": "descripcion", "required": True},
        {"name": "categoria", "required": True},
        {"name": "monto", "required": True, "hint": "decimal"},
        {"name": "proveedor_id", "required": False},
        {"name": "nombre_proveedor", "required": False},
        {"name": "tipo_pago", "required": False},
        {"name": "numero_factura", "required": False},
        {"name": "notas", "required": False},
    ],
    "inventario": [
        {"name": "producto_id", "required": True},
        {"name": "nombre_producto", "required": True},
        {"name": "cantidad_actual", "required": True, "hint": "entero"},
        {"name": "descripcion", "required": False},
        {"name": "categoria", "required": False},
        {"name": "cantidad_minima", "required": False, "hint": "entero"},
        {"name": "unidad_medida", "required": False},
        {"name": "precio_compra", "required": False, "hint": "decimal"},
        {"name": "precio_venta", "required": False, "hint": "decimal"},
        {"name": "proveedor_id", "required": False},
        {"name": "ubicacion", "required": False},
    ],
    "clientes": [
        {"name": "cliente_id", "required": True},
        {"name": "nombre", "required": True},
        {"name": "fecha_registro", "required": True, "hint": "YYYY-MM-DD o DD/MM/YYYY"},
        {"name": "email", "required": False},
        {"name": "telefono", "required": False},
        {"name": "direccion", "required": False},
        {"name": "ciudad", "required": False},
        {"name": "codigo_postal", "required": False},
        {"name": "rfc", "required": False},
        {"name": "tipo_cliente", "required": False},
        {"name": "notas", "required": False},
        {"name": "activo", "required": False, "hint": "true / false"},
    ],
}

# Sinónimos comunes español/inglés → columna destino
SYNONYMS = {
    # Fechas
    "date": "fecha", "fecha_venta": "fecha", "fecha_de_venta": "fecha",
    "date_sale": "fecha", "sale_date": "fecha", "fecha_compra": "fecha",
    "fecha_del_gasto": "fecha", "fecha_gasto": "fecha",
    # Producto
    "product_id": "producto_id", "id_producto": "producto_id",
    "sku": "producto_id", "codigo_producto": "producto_id", "codigo": "producto_id",
    "product_name": "nombre_producto", "nombre_del_producto": "nombre_producto",
    "producto": "nombre_producto", "articulo": "nombre_producto", "item": "nombre_producto",
    # Cantidad
    "quantity": "cantidad", "qty": "cantidad", "unidades": "cantidad",
    "cantidad_vendida": "cantidad", "cant": "cantidad",
    # Precios
    "unit_price": "precio_unitario", "precio": "precio_unitario",
    "price": "precio_unitario", "precio_unit": "precio_unitario",
    # Totales
    "total": "monto_total", "total_amount": "monto_total",
    "importe": "monto_total", "subtotal": "monto_total",
    "importe_total": "monto_total", "monto": "monto_total",
    # Cliente
    "customer_id": "cliente_id", "id_cliente": "cliente_id",
    "cod_cliente": "cliente_id",
    # Categoría
    "category": "categoria", "rubro": "categoria", "tipo": "categoria",
    # Gastos
    "description": "descripcion", "concepto": "descripcion",
    "detalle": "descripcion", "gasto": "descripcion",
    "amount": "monto", "valor": "monto", "costo": "monto", "importe": "monto",
    "supplier_id": "proveedor_id", "id_proveedor": "proveedor_id",
    "supplier_name": "nombre_proveedor", "proveedor": "nombre_proveedor",
    "payment_type": "tipo_pago", "metodo_pago": "tipo_pago",
    "forma_pago": "tipo_pago", "pago": "tipo_pago",
    "invoice_number": "numero_factura", "factura": "numero_factura",
    "num_factura": "numero_factura", "nro_factura": "numero_factura",
    "notes": "notas", "observaciones": "notas", "comentarios": "notas",
    # Inventario
    "stock": "cantidad_actual", "cantidad_en_stock": "cantidad_actual",
    "current_stock": "cantidad_actual", "existencias": "cantidad_actual",
    "existencia": "cantidad_actual", "cant_actual": "cantidad_actual",
    "minimum_stock": "cantidad_minima", "stock_minimo": "cantidad_minima",
    "min_stock": "cantidad_minima", "cant_minima": "cantidad_minima",
    "unit": "unidad_medida", "unidad": "unidad_medida", "uom": "unidad_medida",
    "purchase_price": "precio_compra", "costo_unitario": "precio_compra",
    "cost": "precio_compra", "costo": "precio_compra",
    "sale_price": "precio_venta", "pvp": "precio_venta",
    "sell_price": "precio_venta", "precio_de_venta": "precio_venta",
    "location": "ubicacion", "almacen": "ubicacion", "bodega": "ubicacion",
    # Clientes
    "name": "nombre", "nombre_cliente": "nombre",
    "razon_social": "nombre", "customer_name": "nombre",
    "registration_date": "fecha_registro", "fecha_alta": "fecha_registro",
    "fecha_ingreso": "fecha_registro",
    "phone": "telefono", "tel": "telefono", "celular": "telefono",
    "mobile": "telefono",
    "address": "direccion", "domicilio": "direccion",
    "city": "ciudad", "localidad": "ciudad", "municipio": "ciudad",
    "zip_code": "codigo_postal", "cp": "codigo_postal",
    "postal_code": "codigo_postal", "zip": "codigo_postal",
    "customer_type": "tipo_cliente", "segmento": "tipo_cliente",
    "tipo_de_cliente": "tipo_cliente",
    "active": "activo", "estado": "activo", "is_active": "activo",
    "email_address": "email", "correo": "email", "correo_electronico": "email",
    "tax_id": "rfc", "rfc_fiscal": "rfc",
}


def normalize(text: str) -> str:
    """Normaliza texto: lowercase, sin acentos, _ como separador."""
    text = text.strip().lower()
    nfkd = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in nfkd if not unicodedata.combining(c))
    text = re.sub(r'[\s\-\.]+', '_', text)
    text = re.sub(r'[^a-z0-9_]', '', text)
    return text


def auto_map(
    csv_headers: List[str],
    datasource_type: str,
    saved_mappings: Dict[str, str],
) -> List[dict]:
    """
    Genera sugerencias de mapeo para cada header del CSV.
    Retorna lista de { csv_column, target_column, confidence, method }.
    """
    target_cols = [c["name"] for c in DATASOURCE_COLUMNS[datasource_type]]
    used_targets: Set[str] = set()
    results = []

    norm_to_target = {normalize(t): t for t in target_cols}

    # Pre-filtrar sinónimos relevantes a este datasource
    valid_synonyms = {k: v for k, v in SYNONYMS.items() if v in target_cols}

    for header in csv_headers:
        best = {"csv_column": header, "target_column": None, "confidence": 0.0, "method": "none"}
        norm_header = normalize(header)

        # 1. Exact match
        if header in target_cols and header not in used_targets:
            best = {"csv_column": header, "target_column": header, "confidence": 1.0, "method": "exact"}

        # 2. Normalized match
        elif norm_header in norm_to_target and norm_to_target[norm_header] not in used_targets:
            target = norm_to_target[norm_header]
            best = {"csv_column": header, "target_column": target, "confidence": 0.95, "method": "normalized"}

        # 3. Saved mappings (by original or normalized key)
        elif header in saved_mappings and saved_mappings[header] in target_cols and saved_mappings[header] not in used_targets:
            best = {"csv_column": header, "target_column": saved_mappings[header], "confidence": 0.90, "method": "saved"}
        elif norm_header in saved_mappings and saved_mappings[norm_header] in target_cols and saved_mappings[norm_header] not in used_targets:
            best = {"csv_column": header, "target_column": saved_mappings[norm_header], "confidence": 0.90, "method": "saved"}

        # 4. Synonym match
        elif norm_header in valid_synonyms and valid_synonyms[norm_header] not in used_targets:
            target = valid_synonyms[norm_header]
            best = {"csv_column": header, "target_column": target, "confidence": 0.85, "method": "synonym"}

        else:
            # 5. Fuzzy match
            best_ratio = 0.0
            best_target_fuzzy = None
            for t in target_cols:
                if t in used_targets:
                    continue
                ratio = SequenceMatcher(None, norm_header, normalize(t)).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_target_fuzzy = t
            if best_ratio >= 0.6 and best_target_fuzzy:
                best = {
                    "csv_column": header,
                    "target_column": best_target_fuzzy,
                    "confidence": round(best_ratio * 0.8, 2),
                    "method": "fuzzy",
                }

        if best["target_column"]:
            used_targets.add(best["target_column"])
        results.append(best)

    return results


def detect_structure_change(
    csv_headers: List[str],
    saved_mappings: Dict[str, str],
) -> bool:
    """
    Detecta si la estructura del CSV cambió respecto al mapping guardado.
    Retorna True si hay columnas nuevas o faltantes.
    """
    if not saved_mappings:
        return False

    saved_originals = set(saved_mappings.keys())
    current_headers = set(csv_headers)

    new_cols = current_headers - saved_originals
    missing_cols = saved_originals - current_headers

    return len(new_cols) > 0 or len(missing_cols) > 0
