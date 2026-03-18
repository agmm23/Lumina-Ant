"""
Lumina_Ant - Capa de abstracción de fuentes de datos
Permite leer datos desde CSV, Excel y Google Sheets con una interfaz uniforme.
Después de read() todo se convierte en un pandas DataFrame → mismo pipeline de importación.

Extensibilidad: para agregar una nueva fuente (PostgreSQL, REST API, etc.)
implementa DataSourceReader y registra en create_reader().
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any
import io
import json
import logging

import pandas as pd

logger = logging.getLogger(__name__)


# ── Interfaz base ──────────────────────────────────────────────────────────────

class DataSourceReader(ABC):
    """Interfaz base para todos los lectores de fuentes de datos."""

    @abstractmethod
    def get_sheets(self) -> List[str]:
        """
        Retorna la lista de hojas/tabs disponibles en la fuente.
        Para CSV retorna lista vacía (solo una hoja implícita).
        """
        ...

    @abstractmethod
    def read(self, sheet: Optional[str] = None) -> pd.DataFrame:
        """
        Lee los datos de la fuente y retorna un DataFrame de pandas.
        sheet: nombre de la hoja (para Excel y Google Sheets). None = primera hoja.
        """
        ...

    @abstractmethod
    def get_headers(self, sheet: Optional[str] = None) -> List[str]:
        """
        Retorna solo los nombres de columnas sin cargar todos los datos.
        Útil para el paso de auto-mapping.
        """
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Identificador del tipo de fuente: 'csv', 'excel', 'google_sheets'."""
        ...


# ── CSV ────────────────────────────────────────────────────────────────────────

class CSVReader(DataSourceReader):
    """Lee archivos CSV. Sin selección de hoja."""

    def __init__(self, content: bytes, encoding: str = "utf-8"):
        self._content = content
        self._encoding = encoding

    def get_sheets(self) -> List[str]:
        return []  # CSV no tiene hojas

    def get_headers(self, sheet: Optional[str] = None) -> List[str]:
        # Lee solo la primera línea para eficiencia
        text = self._content[:8192].decode(self._encoding, errors="replace")
        # Remove BOM if present
        if text.startswith("\ufeff"):
            text = text[1:]
        first_line = text.split("\n")[0].strip()
        # Handle quoted headers
        try:
            import csv
            reader = csv.reader([first_line])
            return [h.strip() for h in next(reader)]
        except Exception:
            return [h.strip().strip('"') for h in first_line.split(",")]

    def read(self, sheet: Optional[str] = None) -> pd.DataFrame:
        return pd.read_csv(io.BytesIO(self._content))

    @property
    def source_type(self) -> str:
        return "csv"


# ── Excel ──────────────────────────────────────────────────────────────────────

class ExcelReader(DataSourceReader):
    """
    Lee archivos Excel (.xlsx, .xls) con selección de hoja.
    Requiere openpyxl (ya en requirements.txt).
    """

    def __init__(self, content: bytes):
        self._content = content
        self._file = io.BytesIO(content)

    def get_sheets(self) -> List[str]:
        try:
            xl = pd.ExcelFile(io.BytesIO(self._content))
            return xl.sheet_names
        except Exception as e:
            logger.error(f"Error obteniendo hojas del Excel: {e}")
            raise ValueError(f"No se pudo leer el archivo Excel: {e}")

    def get_headers(self, sheet: Optional[str] = None) -> List[str]:
        df = pd.read_excel(io.BytesIO(self._content), sheet_name=sheet, nrows=0)
        return list(df.columns)

    def read(self, sheet: Optional[str] = None) -> pd.DataFrame:
        return pd.read_excel(io.BytesIO(self._content), sheet_name=sheet)

    @property
    def source_type(self) -> str:
        return "excel"


# ── Google Sheets ──────────────────────────────────────────────────────────────

class GoogleSheetsReader(DataSourceReader):
    """
    Lee hojas de Google Sheets via la API v4.
    Requiere un API key de Google Cloud con la API de Sheets habilitada.
    La hoja debe ser pública o compartida como "Cualquiera con el enlace puede ver".

    Para hojas privadas se puede extender con Service Account en el futuro.
    """

    SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

    def __init__(self, spreadsheet_id: str, api_key: str):
        self._id = spreadsheet_id
        self._key = api_key

    @staticmethod
    def extract_id(url_or_id: str) -> str:
        """
        Extrae el spreadsheet ID de una URL de Google Sheets o lo retorna si ya es un ID.
        URL ejemplo: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0
        """
        if "docs.google.com/spreadsheets" in url_or_id:
            # Extraer la parte /d/{ID}/
            import re
            match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
            if match:
                return match.group(1)
            raise ValueError("No se pudo extraer el ID del URL de Google Sheets.")
        # Asumir que ya es un ID
        return url_or_id.strip()

    def _get(self, path: str, params: dict = None) -> Any:
        """Realiza una petición GET a la Sheets API."""
        import httpx
        base_params = {"key": self._key}
        if params:
            base_params.update(params)
        url = f"{self.SHEETS_API}/{self._id}{path}"
        response = httpx.get(url, params=base_params, timeout=15)
        if response.status_code == 403:
            raise PermissionError(
                "Sin permiso para acceder a esta hoja. "
                "Verifica que la hoja sea pública o compartida con 'Cualquiera con el enlace puede ver'."
            )
        if response.status_code == 404:
            raise ValueError("Spreadsheet no encontrado. Verifica el ID o URL.")
        if response.status_code != 200:
            raise RuntimeError(f"Error de la API de Google Sheets: {response.status_code} — {response.text[:200]}")
        return response.json()

    def get_sheets(self) -> List[str]:
        """Retorna los nombres de todas las hojas (tabs) del spreadsheet."""
        data = self._get("", params={"fields": "sheets.properties"})
        sheets = data.get("sheets", [])
        return [s["properties"]["title"] for s in sheets]

    def get_headers(self, sheet: Optional[str] = None) -> List[str]:
        """Retorna solo la primera fila (headers) de la hoja."""
        range_name = f"'{sheet}'!1:1" if sheet else "1:1"
        data = self._get(f"/values/{range_name}")
        values = data.get("values", [[]])
        return [str(h).strip() for h in (values[0] if values else [])]

    def read(self, sheet: Optional[str] = None) -> pd.DataFrame:
        """Lee todos los datos de la hoja especificada."""
        range_name = f"'{sheet}'" if sheet else None
        path = f"/values/{range_name}" if range_name else "/values/A1:ZZ"
        data = self._get(path)
        values = data.get("values", [])
        if not values:
            return pd.DataFrame()

        headers = [str(h).strip() for h in values[0]]
        rows = values[1:]

        # Normalizar filas con menos columnas que el header
        padded = [row + [""] * (len(headers) - len(row)) for row in rows]
        df = pd.DataFrame(padded, columns=headers)

        # Reemplazar strings vacíos por NaN
        df = df.replace("", pd.NA)
        logger.info(f"Google Sheets leído: {len(df)} filas, {len(headers)} columnas")
        return df

    @property
    def source_type(self) -> str:
        return "google_sheets"


# ── Factory ────────────────────────────────────────────────────────────────────

def create_reader(
    source_type: str,
    content: Optional[bytes] = None,
    config: Optional[dict] = None,
) -> DataSourceReader:
    """
    Crea y retorna el lector apropiado según el tipo de fuente.

    Args:
        source_type: "csv", "excel", "google_sheets"
        content: bytes del archivo (para csv y excel)
        config: dict con parámetros extra:
            - google_sheets: {"spreadsheet_id": "...", "api_key": "..."}
    """
    config = config or {}

    if source_type == "csv":
        if content is None:
            raise ValueError("Se requiere content para fuentes CSV.")
        return CSVReader(content)

    elif source_type == "excel":
        if content is None:
            raise ValueError("Se requiere content para fuentes Excel.")
        return ExcelReader(content)

    elif source_type == "google_sheets":
        spreadsheet_id = config.get("spreadsheet_id")
        api_key = config.get("api_key")
        if not spreadsheet_id:
            raise ValueError("Se requiere 'spreadsheet_id' en config para Google Sheets.")
        if not api_key:
            raise ValueError(
                "Se requiere GOOGLE_SHEETS_API_KEY en .env para importar desde Google Sheets."
            )
        return GoogleSheetsReader(spreadsheet_id, api_key)

    else:
        raise ValueError(
            f"Tipo de fuente desconocido: '{source_type}'. "
            "Opciones válidas: csv, excel, google_sheets"
        )


def detect_source_type(filename: str) -> str:
    """Infiere el tipo de fuente por la extensión del archivo."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
        return "excel"
    return "csv"
