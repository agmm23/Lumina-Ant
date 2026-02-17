"""
Lumina_Ant - Configuración de Base de Datos
Gestiona la conexión a SQLite usando SQLAlchemy
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

# Obtener configuración
settings = get_settings()

# Crear engine de SQLAlchemy
# check_same_thread=False es necesario solo para SQLite
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.debug  # Log de queries SQL en modo debug
)

# Crear SessionLocal para instancias de BD
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base declarativa para los modelos
Base = declarative_base()


def get_db():
    """
    Dependency para obtener sesión de base de datos
    Uso: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
