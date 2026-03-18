# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Lumina Ant — Instrucciones para Claude Code

## Contexto del Proyecto
**Lumina Ant** es un dashboard de Business Intelligence para PYMEs. Permite importar datos de ventas, gastos, inventario y clientes desde múltiples fuentes (CSV, Excel, Google Sheets), visualizarlos con gráficas y KPIs, recibir alertas automáticas de anomalías, y consultar un copiloto de IA en lenguaje natural. La interfaz soporta español e inglés y modo oscuro/claro.

---

## Stack Tecnológico

### Backend — `backend/`
- **FastAPI** + **Uvicorn** (Python), **SQLAlchemy** + **SQLite** (dev)
- **Pandas** para parsing/transformación; **openpyxl** para Excel; **httpx** para Google Sheets API v4
- Arrancar: `cd backend && uvicorn app.main:app --reload` (puerto 8000)

### Frontend — `lumina-frontend/`
- **React 19** + **Vite 7**, **Tailwind CSS v4** (sin `tailwind.config.js`), **Recharts**, **Axios**
- **LanguageContext** + JSON locales (`locales/es.json`, `locales/en.json`) para i18n
- **ThemeContext** para dark/light mode
- Arrancar: `cd lumina-frontend && npm run dev` (puerto 3000)

---

## Comandos de Desarrollo

### Backend
```bash
# Activar entorno virtual (Windows)
cd backend && venv\Scripts\activate

# Arrancar servidor
uvicorn app.main:app --reload          # puerto 8000

# Tests
cd backend && python -m pytest                        # todos los tests
cd backend && python -m pytest tests/test_ventas.py   # un archivo
cd backend && python -m pytest tests/test_ventas.py::test_create_venta  # un test

# Instalar dependencias
pip install -r requirements.txt
```

### Frontend
```bash
cd lumina-frontend && npm run dev      # puerto 3000
cd lumina-frontend && npm run build    # build de producción
cd lumina-frontend && npm run lint     # ESLint
cd lumina-frontend && npm run test     # Vitest (una pasada)
cd lumina-frontend && npm run test:watch  # Vitest en modo watch
```

### Setup inicial de `.env`
```bash
cp backend/.env.example backend/.env
# Editar backend/.env con AI_PROVIDER= y la API key correspondiente
```

---

## Arquitectura de Tests

**Backend** — `backend/tests/` usa `pytest` + `TestClient` de FastAPI con SQLite en memoria:
- `conftest.py` provee fixtures `db` (sesión limpia por test) y `client` (TestClient con DB inyectada + watcher mockeado)
- Factories disponibles: `make_venta`, `make_gasto`, `make_inventario`, `make_cliente`
- Constantes CSV ya formateadas: `VENTAS_CSV`, `GASTOS_CSV`, etc.

**Frontend** — `lumina-frontend/` usa `vitest` + `@testing-library/react` + `jsdom`:
- Tests de componentes en `src/components/__tests__/`
- Setup global en `src/test/setup.js` (si existe)

---

## Estructura de Archivos Clave

```
backend/app/
├── main.py / config.py / database.py
├── models/models.py      # Venta, Gasto, Inventario, Cliente, Alerta,
│                         #   WatchedFile, AlertConfig, ColumnMapping
├── routers/              # ventas, gastos, inventarios, clientes, analytics,
│                         #   chat, import_router, mappings, watcher
├── services/
│   ├── ai_provider.py    # Abstract AIProvider + Claude/OpenAI/Gemini
│   ├── ai_service.py / chat_service.py
│   ├── analytics_service.py  # detección de anomalías, reglas
│   ├── csv_import.py     # parse_*_df(), import_*_rows(), save_and_watch()
│   ├── data_reader.py    # CSVReader, ExcelReader, GoogleSheetsReader
│   └── watcher_service.py    # background asyncio loop
└── schemas/schemas.py

lumina-frontend/src/
├── App.jsx               # Router + ThemeProvider + LanguageProvider
├── contexts/             # ThemeContext.jsx, LanguageContext.jsx
├── locales/              # es.json, en.json
├── pages/                # Dashboard, Ventas, Gastos, Inventario,
│                         #   Clientes, Chat, Configuracion
├── components/           # Sidebar, KpiCard, AlertCard, ColumnMapper...
└── services/api.js       # todos los servicios axios
```

## API Endpoints (puerto 8000)
- `GET /api/analytics/estadisticas` — KPIs globales
- `POST /api/ventas|gastos|inventarios|clientes/upload-csv` — importar CSV/Excel
- `POST /api/import/excel/sheets` — listar hojas Excel
- `POST /api/import/sheets/info|headers|import` — Google Sheets
- `POST /api/chat/` — copiloto IA
- Swagger: http://localhost:8000/docs

## Patrones Clave
- **DataSourceReader**: CSVReader/ExcelReader/GoogleSheetsReader → todos producen `pd.DataFrame`
- **AIProvider**: Claude/OpenAI/Gemini — proveedor activo en `.env` con `AI_PROVIDER=`
- **Watcher**: loop asyncio, polling 5s (local) / 60s (GSheets), detecta cambios por mtime/hash
- **i18n**: `useLanguage()` → `t('key.anidada', {var})`, persistido en `localStorage`
- Path `$alfonso` contiene `$` — en bash siempre escapar: `\$alfonso`
- `tasks/lessons.md` — lecciones aprendidas (formato LXXX); `tasks/todo.md` — registro de tareas completadas

---

## Orquestación del Flujo de Trabajo

### 1. Modo Planificación por Defecto
- Entra en modo planificación para CUALQUIER tarea no trivial (más de 3 pasos o decisiones arquitectónicas)
- Si algo sale mal, PARA y vuelve a planificar de inmediato; no sigas forzando
- Usa el modo planificación para los pasos de verificación, no solo para la construcción
- Escribe especificaciones detalladas por adelantado para reducir la ambigüedad

### 2. Estrategia de Subagentes
- Usa subagentes con frecuencia para mantener limpia la ventana de contexto principal
- Delega la investigación, exploración y análisis paralelo a subagentes
- Para problemas complejos, dedica más capacidad de cómputo mediante subagentes
- Una tarea por subagente para una ejecución focalizada

### 3. Bucle de Automejora
- Al iniciar sesión: leer `tasks/lessons.md` para recordar errores previos
- Tras CUALQUIER corrección del usuario: agregar entrada en `tasks/lessons.md` con formato LXXX
- Registrar tareas completadas en `tasks/todo.md` con archivos tocados y resultado
- Escribe reglas concretas, no principios vagos

### 4. Verificación antes de Finalizar
- Nunca marques una tarea como completada sin demostrar que funciona
- Pregúntate: "¿Aprobaría esto un ingeniero senior?"
- Ejecuta tests, comprueba los logs y demuestra la corrección del código

### 5. Exige Elegancia (Equilibrado)
- Para cambios no triviales: haz una pausa y pregunta "¿hay una forma más elegante?"
- Si un arreglo parece un parche: implementa la solución elegante
- Omite esto para arreglos simples y obvios; no hagas sobreingeniería

### 6. Corrección de Errores Autónoma
- Cuando recibas un informe de error: simplemente arréglalo, no pidas que te lleven de la mano
- Identifica logs, errores o tests que fallan y luego resuélvelos

---

## Gestión de Tareas

1. **Planificar Primero**: Escribe el plan con elementos verificables
2. **Verificar Plan**: Confirma antes de comenzar la implementación
3. **Seguir el Progreso**: Marca los elementos como completados a medida que avances
4. **Explicar Cambios**: Resumen de alto nivel en cada paso
5. **Capturar Lecciones**: Actualiza `tasks/lessons.md` después de las correcciones

---

## Principios Fundamentales

- **Simplicidad Primero**: Haz que cada cambio sea lo más simple posible. Afecta al mínimo código necesario.
- **Sin Pereza**: Encuentra las causas raíz. Nada de arreglos temporales. Estándares de desarrollador senior.
- **Impacto Mínimo**: Los cambios solo deben tocar lo necesario. Evita introducir errores colaterales.

---

## Convenciones del Proyecto
- Componentes React en **PascalCase** (`.jsx`); funciones utilitarias en **camelCase**
- Comentarios en **español**
- Tailwind v4: clases directas, usar prefix `dark:` para modo oscuro
- No usar `pd.read_csv()` directamente en routers — usar `create_reader()` de `data_reader.py`
- Todos los endpoints de upload aceptan `sheet_name: Optional[str] = Form(None)`
