"""
Lumina_Ant - Modelos de Base de Datos
Define las tablas y relaciones usando SQLAlchemy ORM
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Venta(Base):
    """
    Modelo para registros de ventas
    Almacena información de cada transacción de venta
    """
    __tablename__ = "ventas"
    
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, nullable=False, index=True)
    producto_id = Column(String(50), nullable=False, index=True)
    nombre_producto = Column(String(200), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    monto_total = Column(Float, nullable=False)
    cliente_id = Column(String(50), nullable=True)
    categoria = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Venta {self.id}: {self.nombre_producto} - ${self.monto_total}>"


class Alerta(Base):
    """
    Modelo para alertas del sistema
    Registra anomalías y notificaciones detectadas
    """
    __tablename__ = "alertas"
    
    id = Column(Integer, primary_key=True, index=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    tipo = Column(String(50), nullable=False, index=True)  # 'ventas', 'gastos', 'inventario'
    nivel = Column(String(20), nullable=False)  # 'info', 'warning', 'critical'
    mensaje = Column(String(500), nullable=False)
    detalles = Column(String(2000), nullable=True)  # JSON string con info adicional
    leida = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<Alerta {self.id}: {self.tipo} - {self.nivel}>"


class Prediccion(Base):
    """
    Modelo para predicciones generadas
    Almacena pronósticos de ventas y análisis predictivos
    """
    __tablename__ = "predicciones"

    id = Column(Integer, primary_key=True, index=True)
    fecha_generacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_predicha = Column(DateTime, nullable=False)  # Fecha para la cual se predice
    tipo = Column(String(50), nullable=False)  # 'ventas', 'demanda', 'tendencia'
    valor_predicho = Column(Float, nullable=False)
    confianza = Column(Float, nullable=True)  # 0.0 a 1.0
    insights = Column(String(2000), nullable=True)  # JSON string con análisis de IA
    modelo_usado = Column(String(100), nullable=True)  # 'linear', 'arima', 'claude'

    def __repr__(self):
        return f"<Prediccion {self.id}: {self.tipo} - ${self.valor_predicho}>"


class Gasto(Base):
    """
    Modelo para registros de gastos
    Almacena información de gastos operativos de la empresa
    """
    __tablename__ = "gastos"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, nullable=False, index=True)
    descripcion = Column(String(300), nullable=False)
    categoria = Column(String(100), nullable=False, index=True)  # 'personal', 'servicios', 'insumos', 'marketing', 'otros'
    monto = Column(Float, nullable=False)
    proveedor_id = Column(String(50), nullable=True)
    nombre_proveedor = Column(String(200), nullable=True)
    tipo_pago = Column(String(50), nullable=True)  # 'efectivo', 'transferencia', 'tarjeta', 'cheque'
    numero_factura = Column(String(100), nullable=True)
    notas = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Gasto {self.id}: {self.descripcion} - ${self.monto}>"


class Inventario(Base):
    """
    Modelo para control de inventario
    Almacena información de productos en stock
    """
    __tablename__ = "inventario"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(String(50), nullable=False, unique=True, index=True)
    nombre_producto = Column(String(200), nullable=False)
    descripcion = Column(String(500), nullable=True)
    categoria = Column(String(100), nullable=True, index=True)
    cantidad_actual = Column(Integer, nullable=False, default=0)
    cantidad_minima = Column(Integer, nullable=True)  # Para alertas de bajo stock
    unidad_medida = Column(String(50), nullable=True)  # 'unidades', 'kg', 'litros', etc.
    precio_compra = Column(Float, nullable=True)
    precio_venta = Column(Float, nullable=True)
    proveedor_id = Column(String(50), nullable=True)
    ubicacion = Column(String(100), nullable=True)  # Ubicación física en almacén
    ultima_actualizacion = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Inventario {self.id}: {self.nombre_producto} - {self.cantidad_actual} {self.unidad_medida}>"


class Cliente(Base):
    """
    Modelo para gestión de clientes
    Almacena información de clientes del negocio
    """
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(String(50), nullable=False, unique=True, index=True)
    nombre = Column(String(200), nullable=False)
    email = Column(String(200), nullable=True, index=True)
    telefono = Column(String(50), nullable=True)
    direccion = Column(String(300), nullable=True)
    ciudad = Column(String(100), nullable=True)
    codigo_postal = Column(String(20), nullable=True)
    rfc = Column(String(50), nullable=True)  # Para México
    tipo_cliente = Column(String(50), nullable=True)  # 'minorista', 'mayorista', 'corporativo'
    fecha_registro = Column(DateTime, nullable=False, index=True)
    notas = Column(String(500), nullable=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Cliente {self.id}: {self.nombre} ({self.cliente_id})>"
