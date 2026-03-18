# Lumina Ant — Knowledge Base / Fuente de Conocimiento

> **Última actualización:** 2026-02-20
> **Versión:** 0.1.0 — Fase 1
> **Propósito:** Documento de referencia para asistentes de IA. Contiene la arquitectura completa, convenciones, endpoints, modelos y decisiones técnicas del proyecto.

---

## 1. Visión General

**Lumina Ant** es un dashboard de Business Intelligence para PYMEs (pequeñas y medianas empresas). Permite importar datos de negocio via CSV, visualizarlos con KPIs y gráficas interactivas, recibir alertas automáticas por anomalías, y consultar un copilot de IA en lenguaje natural.

**Usuarios objetivo:** Dueños de PYMEs sin equipo de analytics dedicado.

### Funcionalidades principales
1. **Gestión de datos** — Importación CSV con mapeo inteligente de columnas (auto-mapping por similitud, sinónimos y fuzzy matching)
2. **Analytics** — Dashboards con KPIs en tiempo real, gráficas de tendencia (Recharts), filtros por fecha y período
3. **Alertas** — Sistema configurable con 8 reglas de detección de anomalías (ventas bajas, gastos excesivos, stock bajo, etc.)
4. **File Watcher** — Monitoreo automático de archivos CSV para re-importar cambios incrementales
5. **Copilot IA** — Chat con IA que clasifica intención, consulta datos con pandas, y genera respuestas contextualizadas
6. **Multi-proveedor IA** — Soporte para Claude (Anthropic), ChatGPT (OpenAI) y Gemini (Google), intercambiables desde `.env`
7. **i18n** — Interfaz bilingüe español/inglés con context de React y archivos JSON de traducciones
8. **Dark mode** — Tema claro/oscuro persistido en localStorage

---

## 2. Stack Tecnológico

### Backend
| Componente | Tecnología | Versión |
|---|---|---|
| Framework web | FastAPI | 0.115.0 |
| Servidor ASGI | Uvicorn | 0.27.0 |
| ORM | SQLAlchemy | 2.0.36 |
| Base de datos | SQLite | (default dev) |
| Análisis de datos | Pandas | 2.2.0 |
| Numéricos | NumPy | 1.26.3 |
| Validación | Pydantic | 2.9.0 |
| Config | pydantic-settings | 2.5.0 |
| IA - Claude | anthropic | 0.18.0 |
| IA - OpenAI | openai | ≥1.30.0 |
| IA - Gemini | google-genai | ≥1.0.0 |
| HTTP client | httpx | 0.26.0 |

### Frontend
| Componente | Tecnología | Versión |
|---|---|---|
| Framework | React | 19.2.0 |
| Bundler | Vite | 7.3.1 |
| Estilos | Tailwind CSS | v4.1.18 |
| Gráficas | Recharts | 3.7.0 |
| HTTP Client | Axios | 1.13.5 |
| i18n | Custom (Context + JSON) | — |

---

## 3. Estructura de Directorios

```
Lumina_Ant/
├── backend/
│   ├── app/
│   │   ├── main.py                    ← Entry point FastAPI
│   │   ├── config.py                  ← Settings (.env)
│   │   ├── database.py                ← SQLAlchemy engine + session
│   │   ├── models/
│   │   │   └── models.py             ← 8 modelos SQLAlchemy
│   │   ├── schemas/
│   │   │   └── schemas.py            ← Pydantic request/response
│   │   ├── routers/
│   │   │   ├── analytics.py          ← Stats, insights, alertas
│   │   │   ├── ventas.py             ← CRUD + CSV ventas
│   │   │   ├── gastos.py             ← CRUD + CSV gastos
│   │   │   ├── inventarios.py        ← CRUD + CSV inventario
│   │   │   ├── clientes.py           ← CRUD + CSV clientes
│   │   │   ├── chat.py               ← Chat copilot
│   │   │   ├── mappings.py           ← Auto-mapping columnas
│   │   │   └── watcher.py            ← File watcher
│   │   └── services/
│   │       ├── ai_provider.py        ← Abstracción multi-proveedor IA
│   │       ├── ai_service.py         ← Análisis con IA (ventas, gastos, etc.)
│   │       ├── chat_service.py       ← Pipeline del copilot
│   │       ├── claude_service.py     ← (Legacy, referencia)
│   │       ├── analytics_service.py  ← Cálculos estadísticos + anomalías
│   │       ├── csv_import.py         ← Parsing e importación CSV
│   │       ├── mapping_service.py    ← Algoritmos de auto-mapping
│   │       └── watcher_service.py    ← Loop de monitoreo de archivos
│   ├── .env / .env.example
│   ├── requirements.txt
│   └── lumina_ant.db                  ← SQLite (auto-creado)
│
├── lumina-frontend/
│   ├── src/
│   │   ├── main.jsx                   ← React entry point
│   │   ├── App.jsx                    ← Layout + routing por tabs
│   │   ├── index.css                  ← Tailwind CSS v4
│   │   ├── contexts/
│   │   │   ├── ThemeContext.jsx       ← Dark mode (useDark hook)
│   │   │   └── LanguageContext.jsx    ← i18n (useLanguage hook)
│   │   ├── components/
│   │   │   ├── Sidebar.jsx            ← Navegación lateral
│   │   │   ├── KpiCard.jsx            ← Tarjeta KPI reutilizable
│   │   │   ├── AlertCard.jsx          ← Tarjeta de alerta
│   │   │   ├── AlertBadge.jsx         ← Badge de alertas
│   │   │   ├── ColumnMapper.jsx       ← UI de mapeo de columnas CSV
│   │   │   ├── SectionAlerts.jsx      ← Alertas por sección
│   │   │   └── ChatMessage.jsx        ← Burbuja de mensaje chat
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx          ← Dashboard global
│   │   │   ├── Ventas.jsx             ← Página de ventas
│   │   │   ├── Gastos.jsx             ← Página de gastos
│   │   │   ├── Inventario.jsx         ← Página de inventario
│   │   │   ├── Clientes.jsx           ← Página de clientes
│   │   │   ├── Chat.jsx               ← Interfaz del copilot
│   │   │   └── Configuracion.jsx      ← Ajustes (alertas, watcher, idioma)
│   │   ├── services/
│   │   │   └── api.js                 ← Capa Axios (todos los endpoints)
│   │   ├── hooks/
│   │   │   └── useWatcherRefresh.js   ← Auto-refresh por file watcher
│   │   └── locales/
│   │       ├── es.json                ← ~280 keys español
│   │       └── en.json                ← ~280 keys inglés
│   └── package.json
│
├── generate_data.py                    ← Generador de datos de prueba
├── *_ejemplo.csv                       ← CSVs de ejemplo
└── EJECUTAR.md                         ← Instrucciones de ejecución
```

---

## 4. Cómo Ejecutar

```bash
# Backend (puerto 8000)
cd backend
pip install -r requirements.txt    # solo la primera vez
uvicorn app.main:app --reload

# Frontend (puerto 3000)
cd lumina-frontend
npm install                        # solo la primera vez
npm run dev
```

- **Swagger docs:** http://localhost:8000/docs
- **App frontend:** http://localhost:3000

---

## 5. Modelos de Base de Datos

### Venta
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | Auto-increment |
| fecha | DateTime | Fecha de la transacción |
| producto_id | String | Identificador del producto |
| nombre_producto | String | Nombre legible |
| cantidad | Integer | Unidades vendidas |
| precio_unitario | Float | Precio por unidad |
| monto_total | Float | Total de la transacción |
| cliente_id | String (nullable) | Referencia al cliente |
| categoria | String (nullable) | Categoría del producto |
| created_at | DateTime | Timestamp de creación |

### Gasto
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| fecha | DateTime | |
| descripcion | String | Descripción del gasto |
| categoria | String | Categoría (Nómina, Servicios, etc.) |
| monto | Float | Monto del gasto |
| proveedor_id | String (nullable) | |
| nombre_proveedor | String (nullable) | |
| tipo_pago | String (nullable) | Efectivo, Transferencia, etc. |
| numero_factura | String (nullable) | |
| notas | Text (nullable) | |
| created_at | DateTime | |

### Inventario
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| producto_id | String **unique** | Clave natural del producto |
| nombre_producto | String | |
| descripcion | Text (nullable) | |
| categoria | String (nullable) | |
| cantidad_actual | Integer | Stock actual |
| cantidad_minima | Integer (nullable) | Nivel mínimo para alertas |
| unidad_medida | String (nullable) | |
| precio_compra | Float (nullable) | Costo de adquisición |
| precio_venta | Float (nullable) | Precio de venta |
| proveedor_id | String (nullable) | |
| ubicacion | String (nullable) | |
| ultima_actualizacion | DateTime | |
| created_at | DateTime | |

### Cliente
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| cliente_id | String **unique** | ID externo del cliente |
| nombre | String | |
| email | String (nullable) | |
| telefono | String (nullable) | |
| direccion | String (nullable) | |
| ciudad | String (nullable) | |
| codigo_postal | String (nullable) | |
| rfc | String (nullable) | RFC fiscal (México) |
| tipo_cliente | String (nullable) | Segmento (Retail, Mayorista, etc.) |
| fecha_registro | DateTime | |
| notas | Text (nullable) | |
| activo | Boolean | Default True |
| created_at | DateTime | |

### Alerta
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| fecha_creacion | DateTime | |
| tipo | String | ventas, gastos, inventario |
| nivel | String | info, warning, critical |
| rule_id | String (nullable) | ID de la regla que la generó |
| mensaje | String | Mensaje legible |
| detalles | Text (nullable) | JSON con datos adicionales |
| leida | Boolean | Default False |

### AlertConfig
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| rule_id | String **unique** | ventas_caida, gastos_pico, etc. |
| enabled | Boolean | Default True |
| params | String (nullable) | JSON con parámetros configurables |

### ColumnMapping
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| user_id | String | Default "default" |
| datasource_type | String | ventas, gastos, inventario, clientes |
| original_column | String | Nombre original del CSV |
| mapped_column | String | Campo destino en el sistema |
| created_at | DateTime | |

### WatchedFile
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| datasource_type | String **unique** | |
| file_path | String | Ruta al archivo CSV monitoreado |
| enabled | Boolean | Default True |
| last_row_count | Integer (nullable) | Filas en última lectura |
| last_mtime | Float (nullable) | Timestamp de modificación |
| last_imported_at | DateTime (nullable) | |
| last_import_count | Integer (nullable) | Filas importadas |
| last_error | String (nullable) | Último error |
| created_at | DateTime | |

### Prediccion (para uso futuro)
| Campo | Tipo | Notas |
|---|---|---|
| id | Integer PK | |
| fecha_generacion | DateTime | |
| fecha_predicha | DateTime | |
| tipo | String | |
| valor_predicho | Float | |
| confianza | Float (nullable) | |
| insights | Text (nullable) | |
| modelo_usado | String (nullable) | |

---

## 6. API Endpoints

### `GET /` — Health check
### `GET /health` — Health check detallado
### `GET /info` — Info de la app + config activa

### Analytics `/api/analytics`
| Método | Ruta | Descripción |
|---|---|---|
| GET | /stats | Estadísticas básicas de ventas |
| GET | /insights | Insights generados por IA |
| POST | /detect-anomalies | Detectar anomalías y crear alertas |
| GET | /alertas | Listar alertas (filtros: leida, tipo, limit) |
| PATCH | /alertas/{id}/marcar-leida | Marcar alerta como leída |
| GET | /alert-config | Obtener configuración de reglas de alerta |
| PATCH | /alert-config/{rule_id} | Actualizar regla de alerta |
| GET | /top-productos | Top productos vendidos |

### Ventas `/api/ventas`
| Método | Ruta | Descripción |
|---|---|---|
| POST | /upload-csv | Subir CSV de ventas |
| GET | /analytics/resumen | Analytics completos (KPIs, series, categorías, top) |
| GET | / | Listar ventas (paginación + filtros fecha) |
| GET | /{id} | Obtener venta por ID |
| DELETE | /{id} | Eliminar venta |
| GET | /stats/count | Conteo total |

### Gastos `/api/gastos`
| Método | Ruta | Descripción |
|---|---|---|
| POST | /upload-csv | Subir CSV de gastos |
| GET | /analytics/resumen | Analytics completos |
| GET | / | Listar gastos |
| GET | /{id} | Obtener gasto por ID |
| POST | / | Crear gasto manual |
| DELETE | /{id} | Eliminar gasto |
| GET | /stats/count | Conteo total |
| GET | /stats/total-por-categoria | Gastos por categoría |

### Inventario `/api/inventarios`
| Método | Ruta | Descripción |
|---|---|---|
| POST | /upload-csv | Subir CSV (upsert por producto_id) |
| GET | /analytics/resumen | Analytics (KPIs, stock bajo, valor) |
| GET | / | Listar items |
| GET | /{id} | Obtener item por ID |
| GET | /producto/{producto_id} | Buscar por producto_id |
| POST | / | Crear item |
| PATCH | /{id} | Actualizar item |
| DELETE | /{id} | Eliminar item |
| GET | /stats/count | Conteo |
| GET | /stats/bajo-stock | Items bajo stock |
| GET | /stats/valor-inventario | Valor total |

### Clientes `/api/clientes`
| Método | Ruta | Descripción |
|---|---|---|
| POST | /upload-csv | Subir CSV (upsert por cliente_id) |
| GET | /analytics/resumen | Analytics (KPIs, tipos, ciudades) |
| GET | / | Listar clientes |
| GET | /{id} | Obtener por ID interno |
| GET | /buscar/{cliente_id} | Buscar por ID externo |
| POST | / | Crear cliente |
| PATCH | /{id} | Actualizar cliente |
| DELETE | /{id} | Eliminar cliente |
| PATCH | /{id}/desactivar | Desactivar (soft delete) |
| GET | /stats/count | Conteo (total, activos, inactivos) |
| GET | /stats/por-tipo | Clientes por tipo |

### Chat `/api/chat`
| Método | Ruta | Descripción |
|---|---|---|
| POST | / | Enviar mensaje al copilot IA |
| GET | /suggested-prompts | Obtener prompts sugeridos |

### Mappings `/api/mappings`
| Método | Ruta | Descripción |
|---|---|---|
| POST | /auto-map | Auto-mapeo de columnas CSV |
| POST | /{datasource_type} | Guardar mapeo confirmado |

### Watcher `/api/watcher`
| Método | Ruta | Descripción |
|---|---|---|
| GET | /status | Polling ligero (versión + estado) |
| GET | / | Listar watchers |
| PUT | /{datasource_type} | Crear/actualizar watcher |
| PATCH | /{datasource_type} | Habilitar/deshabilitar watcher |
| DELETE | /{datasource_type} | Eliminar watcher |

---

## 7. Arquitectura de IA

### Multi-proveedor (ai_provider.py)
```
AIProvider (ABC)
├── ClaudeProvider    → anthropic SDK
├── OpenAIProvider    → openai SDK
└── GeminiProvider    → google-genai SDK

get_ai_provider() → lee AI_PROVIDER de .env → retorna instancia o None (demo)
```

**Interfaz común:**
- `chat_completion(system_prompt, messages, max_tokens)` → str
- `single_prompt(prompt, max_tokens)` → str
- `provider_name` → str

### Configuración en .env
```bash
AI_PROVIDER=claude          # opciones: claude, openai, gemini
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AI...
```

### Pipeline del Chat/Copilot (chat_service.py)
```
Usuario pregunta → _classify_intent() → _get_table_context(table, db)
→ pandas computa stats → _build_system_prompt(context) → provider.chat_completion()
```

1. **Clasificación de intención** — Keyword matching con scoring (multi-word = más peso). Intenciones: ventas, gastos, inventario, clientes, general.
2. **Retrieval** — Consulta a DB via SQLAlchemy, convierte a DataFrame con pandas.
3. **Compute** — Calcula KPIs, top productos, tendencias mensuales, etc.
4. **Interpret** — Envía stats computados + pregunta al LLM para respuesta conversacional.
5. **Demo mode** — Si no hay API key, genera respuestas template con datos reales.

### AIService (ai_service.py)
Usado por el router de analytics para análisis especializados:
- `analyze_sales(data)` → JSON con resumen, insights, alertas, recomendaciones
- `analyze_expenses(data)` → ídem
- `analyze_inventory(data)` → ídem
- `analyze_customers(data)` → ídem
- `explain_alert(type, context)` → explicación textual

---

## 8. Sistema de Alertas

### Reglas configurables (AlertConfig)
| rule_id | Descripción | Nivel |
|---|---|---|
| ventas_caida | Caída de ventas vs periodo anterior | critical |
| ventas_criticas | Ventas por debajo de umbral mínimo | critical |
| ventas_tendencia | Tendencia negativa sostenida | warning |
| gastos_pico | Pico de gasto inusual | critical |
| gastos_excesivos | Gastos superan % de ventas | warning |
| gastos_tendencia | Tendencia de gastos al alza | warning |
| inventario_bajo | Productos por debajo de stock mínimo | critical |
| inventario_sin_stock | Productos con stock 0 | critical |

Cada regla tiene `enabled` (bool) y `params` (JSON con umbrales configurables).
Se gestionan desde Configuración > Alertas en el frontend.

---

## 9. Sistema i18n

### Arquitectura
- **LanguageContext.jsx** — React Context con `useLanguage()` hook
- **Archivos:** `locales/es.json` y `locales/en.json` (~280 keys cada uno)
- **Persistencia:** `localStorage('lumina_lang')`, default `'es'`
- **Acceso:** `t('sidebar.dashboard')` con dot-notation
- **Interpolación:** `t('dashboard.kpi.transacciones', { n: 150 })` → "150 transacciones"
- **Fallback:** Si no existe en idioma actual → busca en español → retorna la key
- **Locale para Intl:** `es-MX` / `en-US` (para formateo de números y fechas)

### Estructura de keys
```json
{
  "sidebar": { "brand", "dashboard", "ventas", ... },
  "common": { "loading", "error", "desde", "hasta", ... },
  "periods": { "7d", "30d", "3m", ... },
  "dashboard": { "title", "subtitle", "kpi": {...}, "charts": {...}, "alertas": {...} },
  "ventas": { "title", "kpi": {...}, "sections": {...}, "table": {...}, "empty": {...} },
  "gastos": { ... },
  "inventario": { ... },
  "clientes": { ... },
  "chat": { "title", "welcome", "placeholder", ... },
  "config": { "title", "tabs": {...}, "datasources": {...}, "upload": {...}, "alertas": {...}, "language": {...} },
  "alertCard": { ... },
  "columnMapper": { ... }
}
```

---

## 10. Frontend — Providers y Layout

### Provider tree (App.jsx)
```jsx
<LanguageProvider>
  <ThemeProvider>
    <Sidebar />
    <main>
      {/* Renderiza página según activeTab */}
    </main>
  </ThemeProvider>
</LanguageProvider>
```

### Navegación por tabs
| Tab ID | Página | Icono |
|---|---|---|
| dashboard | Dashboard.jsx | 📊 |
| ventas | Ventas.jsx | 💰 |
| gastos | Gastos.jsx | 💸 |
| inventario | Inventario.jsx | 📦 |
| clientes | Clientes.jsx | 👥 |
| chat | Chat.jsx | 🤖 |
| configuracion | Configuracion.jsx | ⚙️ |

### Hooks disponibles
- `useDark()` → `{ isDark, toggleDark }`
- `useLanguage()` → `{ lang, locale, setLang, t }`
- `useWatcherRefresh(callback, interval)` → auto-refresh por file watcher

### Componentes reutilizables
- **KpiCard** — Tarjeta de métrica con icono, label, valor, subtexto, color
- **AlertCard** — Alerta con nivel (critical/warning/info), marca leída
- **AlertBadge** — Badge numérico de alertas pendientes
- **ColumnMapper** — Tabla interactiva de mapeo CSV→campos, con confianza y validación
- **SectionAlerts** — Alertas contextuales por sección
- **ChatMessage** — Burbuja de chat con markdown, badges de data sources, followups

---

## 11. API Service Layer (api.js)

**Base URL:** `http://localhost:8000/api`

```js
analyticsService   → getSalesStats, getAlerts, getInsights, marcarLeida, detectarAnomalias, getAlertConfig, toggleAlertRule, updateAlertParams
ventasService      → getAll, getAnalytics, getCount, uploadCSV
gastosService      → getAll, getAnalytics, getCount, getPorCategoria, uploadCSV
inventarioService  → getAll, getAnalytics, getCount, getLowStock, getValor, uploadCSV
clientesService    → getAll, getAnalytics, getCount, getPorTipo, uploadCSV
chatService        → send, getSuggestedPrompts
mappingService     → autoMap, save
watcherService     → getStatus, list, upsert, patch, remove
```

---

## 12. Convenciones de Código

### Backend (Python)
- **Docstrings** en español para funciones públicas
- **Logs** con `logger` (logging estándar de Python)
- **Nombres de variables** en español para dominio de negocio (venta, gasto, cliente...)
- **Nombres de funciones** en inglés/español mezclado (convención del proyecto)
- **Error handling** con try/except y respuestas graceful (no crashea)
- **Demo mode** en todos los servicios de IA — funciona sin API key

### Frontend (React/JSX)
- **Functional components** con hooks (no clases)
- **Tailwind CSS v4** para estilos (utility-first, no CSS modules)
- **useLanguage** obligatorio en cada componente con texto visible
- **Dark mode** via `isDark` condicional en classNames
- **Recharts** para gráficas (BarChart, LineChart, PieChart, AreaChart)
- **Estado local** con `useState` + `useEffect` para fetch de datos
- **No hay router** — navegación por tabs con `activeTab` state en App.jsx

---

## 13. Flujo de Importación CSV

```
1. Usuario arrastra CSV en Configuración
2. Frontend detecta archivo → llama POST /api/mappings/auto-map
3. Backend analiza headers → retorna sugerencias de mapeo (exact, normalized, synonym, fuzzy)
4. ColumnMapper muestra mapeo → usuario confirma/ajusta
5. Frontend envía CSV + mapping → POST /api/{datasource}/upload-csv
6. Backend parsea CSV con mapping → inserta/upserta en DB
7. Si watcher habilitado → copia CSV a watched_data/ → monitoreo incremental
```

### Algoritmos de auto-mapping (mapping_service.py)
1. **Exact** — coincidencia exacta con campo destino
2. **Normalized** — lowercase, sin acentos, sin espacios
3. **Saved** — mapeo guardado previamente por el usuario
4. **Synonym** — diccionario de sinónimos por idioma (fecha → date, monto → amount...)
5. **Fuzzy** — similitud de cadena (Levenshtein-like) para coincidencias parciales

---

## 14. Variables de Entorno (.env)

```bash
# App
APP_NAME=Lumina_Ant
VERSION=1.0.0
DEBUG=True

# DB
DATABASE_URL=sqlite:///./lumina_ant.db

# Proveedor de IA: "claude" | "openai" | "gemini"
AI_PROVIDER=claude

# API Keys (solo la del proveedor activo)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Modelos (opcionales, tienen defaults)
CLAUDE_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o
GEMINI_MODEL=gemini-2.0-flash

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

---

## 15. Reglas de Negocio Importantes

1. **Los datos del backend (nombres de productos, categorías, etc.) NO se traducen** — solo la UI.
2. **Inventario y Clientes usan upsert** — si el `producto_id` o `cliente_id` ya existe, se actualiza en vez de duplicar.
3. **Las alertas se generan por detección de anomalías** vía `POST /detect-anomalies`, no en tiempo real.
4. **El watcher service corre en background** con un loop asyncio que verifica cambios en archivos monitoreados cada N segundos.
5. **El chat copilot clasifica intención sin LLM** (keyword matching) para evitar llamadas innecesarias a la API.
6. **Sin API key = modo demo** — todas las funciones de IA retornan respuestas basadas en datos reales pero con templates predefinidos.
7. **El frontend no tiene router** (react-router) — usa un simple `activeTab` state, suficiente para la cantidad actual de páginas.
8. **pydantic-settings** lee automáticamente del archivo `.env` — las variables comentadas (`# OPENAI_API_KEY=`) son ignoradas y toman el valor default (`""`).

---

## 16. Roadmap / Pendientes

- [ ] **RAG (Retrieval-Augmented Generation)** — Indexar datos para búsqueda semántica
- [ ] **Predicciones** — Modelo `Prediccion` existe en DB pero no se usa aún
- [ ] **MySQL en producción** — Migrar de SQLite a MySQL (config ya preparada en .env)
- [ ] **Exportar reportes** — PDF/Excel de dashboards
- [ ] **Autenticación** — Sin auth actualmente, todo es público/local
- [ ] **Más idiomas** — Estructura i18n soporta N idiomas, solo hay es/en
