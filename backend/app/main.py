"""
Lumina_Ant - Aplicación Principal
API REST para análisis de ventas con IA para PYMEs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import get_settings
from app.database import engine, Base
import asyncio
from app.routers import ventas, analytics, gastos, inventarios, clientes, mappings, watcher
from app.services.watcher_service import watcher_loop

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)
logger.info("Tablas de base de datos creadas/verificadas")

# Obtener configuración
settings = get_settings()

# Crear aplicación FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="""
    ## Lumina_Ant - Analytics API

    API REST para análisis inteligente de datos empresariales usando IA.

    ### Funcionalidades principales:

    * **Ventas**: Carga y gestión de datos de ventas
    * **Gastos**: Control y análisis de gastos operativos
    * **Inventario**: Gestión de stock y productos
    * **Clientes**: Administración de base de clientes (CRM)
    * **Analytics**: Estadísticas y métricas clave
    * **IA**: Insights y recomendaciones generadas por Claude
    * **Alertas**: Detección automática de anomalías

    ### Desarrollado para PYMEs

    Ayuda a pequeñas y medianas empresas a tomar decisiones basadas en datos,
    sin necesidad de equipos de análisis especializados.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS configurado para: {settings.cors_origins}")

# Incluir routers
app.include_router(ventas.router)
app.include_router(gastos.router)
app.include_router(inventarios.router)
app.include_router(clientes.router)
app.include_router(analytics.router)
app.include_router(mappings.router)
app.include_router(watcher.router)

logger.info("Routers registrados: ventas, gastos, inventarios, clientes, analytics, mappings, watcher")


# Endpoints raíz

@app.get("/")
def read_root():
    """
    Endpoint raíz con información del API
    """
    return {
        "app": settings.app_name,
        "version": settings.version,
        "status": "running",
        "endpoints": {
            "documentación": "/docs",
            "documentación_alternativa": "/redoc",
            "health_check": "/health",
            "ventas": "/api/ventas",
            "gastos": "/api/gastos",
            "inventarios": "/api/inventarios",
            "clientes": "/api/clientes",
            "analytics": "/api/analytics"
        },
        "features": [
            "Carga de ventas, gastos, inventario y clientes desde CSV",
            "Gestión completa de datasources para PyMEs",
            "Estadísticas en tiempo real por módulo",
            "Insights generados por IA para cada datasource",
            "Detección automática de anomalías",
            "Sistema de alertas inteligente",
            "Control de inventario con alertas de stock",
            "CRM básico para gestión de clientes"
        ]
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint para monitoreo
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.version
    }


@app.get("/info")
def app_info():
    """
    Información detallada de la aplicación
    """
    return {
        "name": settings.app_name,
        "version": settings.version,
        "debug_mode": settings.debug,
        "database": "SQLite" if "sqlite" in settings.database_url else "Unknown",
        "ai_provider": "Anthropic Claude",
        "datasources": {
            "ventas": True,
            "gastos": True,
            "inventario": True,
            "clientes": True
        },
        "features": {
            "ventas_crud": True,
            "gastos_crud": True,
            "inventario_crud": True,
            "clientes_crud": True,
            "csv_upload": True,
            "analytics": True,
            "ai_insights": True,
            "anomaly_detection": True,
            "alerts": True,
            "stock_alerts": True,
            "customer_management": True
        }
    }


# Event handlers

_watcher_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup_event():
    """
    Acciones al iniciar la aplicación
    """
    global _watcher_task
    logger.info(f"🚀 {settings.app_name} v{settings.version} iniciada")
    logger.info(f"📊 Base de datos: {settings.database_url}")
    logger.info(f"🤖 IA: {'Configurada' if settings.anthropic_api_key else 'No configurada'}")
    _watcher_task = asyncio.create_task(watcher_loop())
    logger.info("✅ Aplicación lista para recibir requests")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Acciones al cerrar la aplicación
    """
    global _watcher_task
    if _watcher_task:
        _watcher_task.cancel()
    logger.info("👋 Cerrando aplicación Lumina_Ant")


# Main para ejecutar directamente
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
