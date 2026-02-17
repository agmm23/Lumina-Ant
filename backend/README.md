# 🌟 Lumina_Ant

**Plataforma Integral de Análisis Empresarial con IA para PYMEs**

Sistema inteligente que ayuda a pequeñas y medianas empresas a gestionar y analizar sus datos de ventas, gastos, inventario y clientes, detectar anomalías y obtener insights accionables usando Inteligencia Artificial.

---

## ✨ Características

### 📊 Gestión Integral de Datos
- **Ventas**: Seguimiento de transacciones y análisis de ingresos
- **Gastos**: Control de egresos y gestión de proveedores
- **Inventario**: Control de stock con alertas de reabastecimiento
- **Clientes**: CRM básico para gestión de relaciones

### 🤖 Inteligencia Artificial
- **Insights por Datasource**: Análisis específico para cada módulo
- **Detección de Anomalías**: Alertas automáticas ante patrones inusuales
- **Recomendaciones Accionables**: Sugerencias personalizadas por IA

### 📈 Analytics y Reportes
- **KPIs en Tiempo Real**: Métricas clave por categoría
- **Estadísticas Avanzadas**: Análisis de tendencias y patrones
- **Alertas Inteligentes**: Notificaciones automáticas

### 📁 Importación Masiva
- **Carga CSV**: Importación rápida para todos los datasources
- **Actualización Automática**: Merge inteligente de datos existentes

---

## 🚀 Inicio Rápido

### Requisitos Previos

- Python 3.11 o superior
- pip (gestor de paquetes de Python)
- API Key de Anthropic ([obtener aquí](https://console.anthropic.com/settings/keys))

### Instalación

1. **Clonar o descargar el proyecto**

```bash
cd Lumina_Ant/backend
```

2. **Crear entorno virtual**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

3. **Instalar dependencias**

```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**

```bash
# Copiar el archivo de ejemplo
copy .env.example .env     # Windows
cp .env.example .env       # Mac/Linux

# Editar .env y agregar tu API key de Anthropic
notepad .env               # Windows
nano .env                  # Mac/Linux
```

**Contenido de .env:**
```env
ANTHROPIC_API_KEY=sk-ant-api03-tu-key-aqui
DEBUG=True
DATABASE_URL=sqlite:///./lumina_ant.db
```

5. **Ejecutar la aplicación**

```bash
python -m uvicorn app.main:app --reload
```

La aplicación estará disponible en: **http://localhost:8000**

---

## 📖 Documentación del API

Una vez iniciada la aplicación, puedes acceder a:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🎯 Uso Básico

### 1. Cargar Datos

El sistema incluye archivos CSV de ejemplo en la raíz del proyecto:
- `ventas_ejemplo.csv` - Datos de ventas
- `gastos_ejemplo.csv` - Datos de gastos
- `inventario_ejemplo.csv` - Datos de inventario
- `clientes_ejemplo.csv` - Datos de clientes

#### Cargar Ventas

```csv
fecha,producto_id,nombre_producto,cantidad,precio_unitario,monto_total,cliente_id,categoria
2024-02-01,P001,Laptop Dell,2,850.00,1700.00,C001,Electrónica
```

```bash
curl -X POST "http://localhost:8000/api/ventas/upload-csv" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@ventas_ejemplo.csv"
```

#### Cargar Gastos

```csv
fecha,descripcion,categoria,monto,proveedor_id,nombre_proveedor,tipo_pago,numero_factura
2024-02-01,Renta de oficina,Servicios,15000.00,PROV001,Inmobiliaria Centro,transferencia,FACT-001
```

```bash
curl -X POST "http://localhost:8000/api/gastos/upload-csv" \
  -F "file=@gastos_ejemplo.csv"
```

#### Cargar Inventario

```csv
producto_id,nombre_producto,descripcion,categoria,cantidad_actual,cantidad_minima,unidad_medida,precio_compra,precio_venta
P001,Laptop Dell,Laptop 15 pulgadas,Electrónica,25,5,unidades,680.00,850.00
```

```bash
curl -X POST "http://localhost:8000/api/inventarios/upload-csv" \
  -F "file=@inventario_ejemplo.csv"
```

#### Cargar Clientes

```csv
cliente_id,nombre,email,telefono,fecha_registro,tipo_cliente,activo
C001,Tecnología Empresarial SA,contacto@tecempresa.mx,555-1234-5678,2023-06-15,corporativo,true
```

```bash
curl -X POST "http://localhost:8000/api/clientes/upload-csv" \
  -F "file=@clientes_ejemplo.csv"
```

O usa la interfaz interactiva de Swagger en `/docs`

### 2. Obtener Estadísticas

```bash
curl http://localhost:8000/api/analytics/stats
```

**Respuesta:**
```json
{
  "total_ventas": 15420.50,
  "cantidad_transacciones": 45,
  "ticket_promedio": 342.68,
  "producto_mas_vendido": "Laptop Dell",
  "categoria_principal": "Electrónica"
}
```

### 3. Generar Insights con IA

```bash
curl http://localhost:8000/api/analytics/insights
```

**Respuesta:**
```json
{
  "resumen": "Las ventas muestran un crecimiento del 15% en los últimos 7 días...",
  "insights": [
    "El producto 'Laptop Dell' representa el 45% de las ventas totales",
    "Las ventas de accesorios han crecido un 20% esta semana",
    "El ticket promedio aumentó de $300 a $342"
  ],
  "alertas": [
    "Inventario bajo detectado en Mouse Logitech"
  ],
  "recomendaciones": [
    "Aumentar stock de productos top antes del fin de semana",
    "Crear promoción para categoría Accesorios"
  ]
}
```

### 4. Detectar Anomalías

```bash
curl -X POST http://localhost:8000/api/analytics/detect-anomalies
```

---

## 📁 Estructura del Proyecto

```
Lumina_Ant/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # Aplicación FastAPI principal
│   │   ├── config.py            # Configuración y variables de entorno
│   │   ├── database.py          # Configuración de SQLAlchemy
│   │   ├── models/
│   │   │   └── models.py        # Modelos de base de datos (Venta, Gasto, Inventario, Cliente, etc.)
│   │   ├── schemas/
│   │   │   └── schemas.py       # Schemas de Pydantic para validación
│   │   ├── routers/
│   │   │   ├── ventas.py        # Endpoints de ventas
│   │   │   ├── gastos.py        # Endpoints de gastos
│   │   │   ├── inventarios.py   # Endpoints de inventario
│   │   │   ├── clientes.py      # Endpoints de clientes
│   │   │   └── analytics.py     # Endpoints de análisis
│   │   └── services/
│   │       ├── claude_service.py    # Integración con Claude AI
│   │       └── analytics_service.py # Lógica de análisis
│   ├── requirements.txt         # Dependencias
│   ├── .env.example            # Template de variables de entorno
│   ├── .gitignore
│   └── README.md
├── ventas_ejemplo.csv          # Datos de ejemplo - Ventas
├── gastos_ejemplo.csv          # Datos de ejemplo - Gastos
├── inventario_ejemplo.csv      # Datos de ejemplo - Inventario
└── clientes_ejemplo.csv        # Datos de ejemplo - Clientes
```

---

## 🔌 Endpoints Principales

### Ventas

- `POST /api/ventas/upload-csv` - Cargar archivo CSV con ventas
- `GET /api/ventas` - Listar ventas (paginado)
- `GET /api/ventas/{id}` - Obtener una venta específica
- `DELETE /api/ventas/{id}` - Eliminar una venta
- `GET /api/ventas/stats/count` - Conteo total de ventas

### Gastos

- `POST /api/gastos/upload-csv` - Cargar archivo CSV con gastos
- `GET /api/gastos` - Listar gastos (paginado)
- `GET /api/gastos/{id}` - Obtener un gasto específico
- `POST /api/gastos` - Crear gasto manualmente
- `DELETE /api/gastos/{id}` - Eliminar un gasto
- `GET /api/gastos/stats/count` - Conteo total de gastos
- `GET /api/gastos/stats/total-por-categoria` - Gastos agrupados por categoría

### Inventario

- `POST /api/inventarios/upload-csv` - Cargar/actualizar inventario desde CSV
- `GET /api/inventarios` - Listar items de inventario (paginado)
- `GET /api/inventarios/{id}` - Obtener item por ID
- `GET /api/inventarios/producto/{producto_id}` - Buscar por producto_id
- `POST /api/inventarios` - Crear nuevo item
- `PATCH /api/inventarios/{id}` - Actualizar item
- `DELETE /api/inventarios/{id}` - Eliminar item
- `GET /api/inventarios/stats/bajo-stock` - Items con stock bajo
- `GET /api/inventarios/stats/valor-inventario` - Valor total del inventario

### Clientes

- `POST /api/clientes/upload-csv` - Cargar/actualizar clientes desde CSV
- `GET /api/clientes` - Listar clientes (paginado, solo activos por defecto)
- `GET /api/clientes/{id}` - Obtener cliente por ID
- `GET /api/clientes/buscar/{cliente_id}` - Buscar por cliente_id externo
- `POST /api/clientes` - Crear nuevo cliente
- `PATCH /api/clientes/{id}` - Actualizar cliente
- `DELETE /api/clientes/{id}` - Eliminar cliente
- `PATCH /api/clientes/{id}/desactivar` - Desactivar cliente
- `GET /api/clientes/stats/count` - Conteo total y activos
- `GET /api/clientes/stats/por-tipo` - Clientes agrupados por tipo

### Analytics

- `GET /api/analytics/stats` - Estadísticas básicas de ventas
- `GET /api/analytics/insights` - Insights generados por IA
- `POST /api/analytics/detect-anomalies` - Detectar anomalías
- `GET /api/analytics/alertas` - Listar alertas
- `PATCH /api/analytics/alertas/{id}/marcar-leida` - Marcar alerta como leída
- `GET /api/analytics/top-productos` - Top productos más vendidos

### General

- `GET /` - Información del API
- `GET /health` - Health check
- `GET /info` - Información detallada

---

## 🛠️ Tecnologías

- **Framework**: FastAPI
- **Base de Datos**: SQLite (migrable a MySQL/PostgreSQL)
- **ORM**: SQLAlchemy
- **Análisis de Datos**: pandas, numpy
- **IA**: Anthropic Claude API
- **Validación**: Pydantic

---

## 🔐 Seguridad

- Las API keys nunca deben committearse al repositorio
- Usar `.env` para variables sensibles
- El archivo `.env` está en `.gitignore`
- CORS configurado para orígenes específicos

---

## 📊 Base de Datos

### Modelos Principales

**Venta**
- Información de transacciones de venta
- Campos: fecha, producto_id, nombre_producto, cantidad, precio_unitario, monto_total, cliente_id, categoria

**Gasto**
- Registro de egresos y gastos operativos
- Campos: fecha, descripcion, categoria, monto, proveedor_id, nombre_proveedor, tipo_pago, numero_factura

**Inventario**
- Control de stock y productos
- Campos: producto_id (único), nombre_producto, cantidad_actual, cantidad_minima, precio_compra, precio_venta, ubicacion

**Cliente**
- Gestión de clientes (CRM)
- Campos: cliente_id (único), nombre, email, telefono, direccion, rfc, tipo_cliente, fecha_registro, activo

**Alerta**
- Notificaciones automáticas del sistema
- Tipos: ventas, gastos, inventario
- Niveles: info, warning, critical

**Prediccion**
- Pronósticos y análisis predictivos
- Modelos predictivos para ventas y demanda

### Migración a Producción

Para usar MySQL en lugar de SQLite:

1. Instalar driver:
```bash
pip install pymysql
```

2. Actualizar `DATABASE_URL` en `.env`:
```env
DATABASE_URL=mysql+pymysql://usuario:password@localhost/lumina_ant
```

---

## 🐛 Troubleshooting

### Error: "No module named 'app'"

Asegúrate de estar en la carpeta `/backend` y ejecutar:
```bash
python -m uvicorn app.main:app --reload
```

### Error: "API key not configured"

Verifica que tu `.env` tenga la API key correcta:
```env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### Error al importar CSV

- Verifica que el archivo tenga las columnas requeridas
- Las fechas deben estar en formato YYYY-MM-DD o DD/MM/YYYY
- Los montos deben ser números (usar punto como decimal)

---

## 🚀 Próximas Funcionalidades

- [ ] Predicciones de ventas con ML
- [ ] Dashboard web con React
- [ ] Integración con Excel directo
- [ ] Alertas por email/WhatsApp
- [ ] Reportes PDF automatizados
- [ ] Multi-usuario y permisos
- [ ] Análisis cruzado (ventas vs gastos vs inventario)
- [ ] Integración con sistemas contables
- [ ] App móvil para consultas
- [ ] Exportación de reportes personalizados

---

## 👨‍💻 Desarrollo

### Ejecutar en modo desarrollo

```bash
uvicorn app.main:app --reload --log-level debug
```

### Testing (próximamente)

```bash
pytest
```

---

## 📝 Licencia

Proyecto privado - Lumina_Ant

---

## 🤝 Soporte

Para dudas o problemas:
- Revisar la documentación en `/docs`
- Verificar logs de la aplicación
- Consultar el código de ejemplo en `ventas_ejemplo.csv`

---

## 🎓 Aprender Más

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [pandas Documentation](https://pandas.pydata.org/docs/)

---

**¡Hecho con ❤️ para PYMEs!**
