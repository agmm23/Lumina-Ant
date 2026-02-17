"""
Lumina_Ant - Configuración de la aplicación
Gestiona todas las variables de entorno y configuraciones globales
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Configuración de la aplicación usando variables de entorno"""
    
    # Información de la aplicación
    app_name: str = "Lumina_Ant - Analytics API"
    version: str = "1.0.0"
    debug: bool = True
    
    # Base de datos
    database_url: str = "sqlite:///./lumina_ant.db"
    
    # API de Anthropic Claude
    anthropic_api_key: str = ""
    
    # CORS - Orígenes permitidos
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Obtiene la configuración de la aplicación (cached)
    El decorador lru_cache asegura que solo se cree una instancia
    """
    return Settings()
