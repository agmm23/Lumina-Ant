"""
Lumina_Ant - Schemas de Pydantic
Define los modelos de validación para requests/responses del API
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


# ==================== VENTAS ====================

class VentaBase(BaseModel):
    """Schema base para Venta"""
    fecha: datetime
    producto_id: str
    nombre_producto: str
    cantidad: int = Field(gt=0, description="Cantidad debe ser mayor a 0")
    precio_unitario: float = Field(gt=0, description="Precio debe ser mayor a 0")
    monto_total: float = Field(gt=0, description="Monto total debe ser mayor a 0")
    cliente_id: Optional[str] = None
    categoria: Optional[str] = None


class VentaCreate(VentaBase):
    """Schema para crear una nueva venta"""
    pass


class Venta(VentaBase):
    """Schema completo de Venta (con id)"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== ALERTAS ====================

class AlertaBase(BaseModel):
    """Schema base para Alerta"""
    tipo: str = Field(..., description="Tipo de alerta: ventas, gastos, inventario")
    nivel: str = Field(..., description="Nivel: info, warning, critical")
    mensaje: str = Field(..., max_length=500)
    detalles: Optional[str] = None


class AlertaCreate(AlertaBase):
    """Schema para crear una nueva alerta"""
    pass


class Alerta(AlertaBase):
    """Schema completo de Alerta (con id)"""
    id: int
    fecha_creacion: datetime
    rule_id: Optional[str] = None
    leida: bool
    
    class Config:
        from_attributes = True


# ==================== PREDICCIONES ====================

class PrediccionBase(BaseModel):
    """Schema base para Predicción"""
    fecha_predicha: datetime
    tipo: str
    valor_predicho: float
    confianza: Optional[float] = Field(None, ge=0.0, le=1.0)
    insights: Optional[str] = None
    modelo_usado: Optional[str] = None


class PrediccionCreate(PrediccionBase):
    """Schema para crear una nueva predicción"""
    pass


class Prediccion(PrediccionBase):
    """Schema completo de Predicción (con id)"""
    id: int
    fecha_generacion: datetime
    
    class Config:
        from_attributes = True


# ==================== ANALYTICS ====================

class VentasStats(BaseModel):
    """Estadísticas básicas de ventas"""
    total_ventas: float
    cantidad_transacciones: int
    ticket_promedio: float
    producto_mas_vendido: str
    categoria_principal: str


class InsightResponse(BaseModel):
    """Respuesta con insights generados por IA"""
    resumen: str
    insights: List[str]
    alertas: List[str]
    recomendaciones: List[str]


# ==================== GASTOS ====================

class GastoBase(BaseModel):
    """Schema base para Gasto"""
    fecha: datetime
    descripcion: str = Field(..., max_length=300)
    categoria: str = Field(..., max_length=100)
    monto: float = Field(gt=0, description="Monto debe ser mayor a 0")
    proveedor_id: Optional[str] = None
    nombre_proveedor: Optional[str] = None
    tipo_pago: Optional[str] = None
    numero_factura: Optional[str] = None
    notas: Optional[str] = None


class GastoCreate(GastoBase):
    """Schema para crear un nuevo gasto"""
    pass


class Gasto(GastoBase):
    """Schema completo de Gasto (con id)"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== INVENTARIO ====================

class InventarioBase(BaseModel):
    """Schema base para Inventario"""
    producto_id: str = Field(..., max_length=50)
    nombre_producto: str = Field(..., max_length=200)
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    cantidad_actual: int = Field(ge=0, description="Cantidad debe ser mayor o igual a 0")
    cantidad_minima: Optional[int] = Field(None, ge=0)
    unidad_medida: Optional[str] = None
    precio_compra: Optional[float] = Field(None, ge=0)
    precio_venta: Optional[float] = Field(None, ge=0)
    proveedor_id: Optional[str] = None
    ubicacion: Optional[str] = None


class InventarioCreate(InventarioBase):
    """Schema para crear un nuevo item de inventario"""
    pass


class InventarioUpdate(BaseModel):
    """Schema para actualizar inventario (campos opcionales)"""
    nombre_producto: Optional[str] = None
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    cantidad_actual: Optional[int] = Field(None, ge=0)
    cantidad_minima: Optional[int] = Field(None, ge=0)
    unidad_medida: Optional[str] = None
    precio_compra: Optional[float] = Field(None, ge=0)
    precio_venta: Optional[float] = Field(None, ge=0)
    proveedor_id: Optional[str] = None
    ubicacion: Optional[str] = None


class Inventario(InventarioBase):
    """Schema completo de Inventario (con id)"""
    id: int
    ultima_actualizacion: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== CLIENTES ====================

class ClienteBase(BaseModel):
    """Schema base para Cliente"""
    cliente_id: str = Field(..., max_length=50)
    nombre: str = Field(..., max_length=200)
    email: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    codigo_postal: Optional[str] = None
    rfc: Optional[str] = None
    tipo_cliente: Optional[str] = None
    fecha_registro: datetime
    notas: Optional[str] = None
    activo: bool = True


class ClienteCreate(ClienteBase):
    """Schema para crear un nuevo cliente"""
    pass


class ClienteUpdate(BaseModel):
    """Schema para actualizar cliente (campos opcionales)"""
    nombre: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    codigo_postal: Optional[str] = None
    rfc: Optional[str] = None
    tipo_cliente: Optional[str] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None


class Cliente(ClienteBase):
    """Schema completo de Cliente (con id)"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== COLUMN MAPPING ====================

class AutoMapRequest(BaseModel):
    """Request para auto-mapear headers CSV a columnas destino"""
    headers: List[str]
    datasource_type: str = Field(..., pattern="^(ventas|gastos|inventario|clientes)$")
    user_id: str = "default"


class ColumnMappingSuggestion(BaseModel):
    """Una sugerencia de mapeo individual"""
    csv_column: str
    target_column: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    method: str  # 'exact', 'normalized', 'saved', 'synonym', 'fuzzy', 'none'


class AutoMapResponse(BaseModel):
    """Respuesta con sugerencias de auto-mapeo"""
    mappings: List[ColumnMappingSuggestion]
    all_mapped: bool
    unmapped_required: List[str]
    target_columns: List[dict]
    has_saved_mappings: bool  # True si el usuario ya tiene mappings guardados para este datasource
    structure_changed: bool  # True si las columnas del CSV difieren del mapping guardado


class SaveMappingRequest(BaseModel):
    """Request para guardar mappings confirmados"""
    mappings: dict
    user_id: str = "default"


# ==================== ANALYTICS AGGREGATION ====================

class TimeSeriesPoint(BaseModel):
    """Punto de una serie temporal (día/semana/mes)"""
    fecha: str
    total: float

class CategoryBreakdown(BaseModel):
    """Desglose por categoría"""
    categoria: str
    total: float

class TopItem(BaseModel):
    """Item con nombre y monto (producto, proveedor, etc.)"""
    nombre: str
    monto: float

class VentasAnalytics(BaseModel):
    """Payload completo de analytics para la página de Ventas"""
    total_ventas: float
    num_transacciones: int
    ticket_promedio: float
    top_producto: str
    top_categoria: str
    serie_temporal: List[TimeSeriesPoint]
    por_categoria: List[CategoryBreakdown]
    top_productos: List[TopItem]

class GastosAnalytics(BaseModel):
    """Payload completo de analytics para la página de Gastos"""
    total_gastos: float
    num_registros: int
    gasto_promedio: float
    top_categoria: str
    top_tipo_pago: str
    serie_temporal: List[TimeSeriesPoint]
    por_categoria: List[CategoryBreakdown]
    top_proveedores: List[TopItem]

class CiudadCount(BaseModel):
    """Conteo de clientes por ciudad"""
    ciudad: str
    cantidad: int


# ==================== RESPONSES ====================

class MessageResponse(BaseModel):
    """Respuesta genérica con mensaje"""
    status: str
    message: str
    data: Optional[dict] = None
