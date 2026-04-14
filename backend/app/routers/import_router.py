"""
Lumina_Ant - Router de Importación de Fuentes de Datos
Endpoints auxiliares para listar hojas y obtener headers antes del upload.
Soporta: Excel (.xlsx/.xls) y Google Sheets.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.csv_import import (
    parse_ventas_df, import_ventas_rows,
    parse_gastos_df, import_gastos_rows,
    parse_inventario_df, import_inventario_rows,
    parse_clientes_df, import_clientes_rows,
    save_and_watch,
)
from app.services.data_reader import (
    ExcelReader,
    GoogleSheetsReader,
    detect_source_type,
)
from app.services.watcher_service import bump_import_version
from app.auth.dependencies import get_current_user
from app.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["import"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class SheetListResponse(BaseModel):
    sheets: List[str]
    spreadsheet_id: Optional[str] = None
    title: Optional[str] = None


class HeadersResponse(BaseModel):
    headers: List[str]
    sheet: Optional[str] = None


class SheetsInfoRequest(BaseModel):
    url_or_id: str


class SheetsHeadersRequest(BaseModel):
    spreadsheet_id: str
    sheet: Optional[str] = None


class SheetsImportRequest(BaseModel):
    spreadsheet_id: str
    sheet: Optional[str] = None
    datasource_type: str  # "ventas" | "gastos" | "inventario" | "clientes"
    column_mapping: Optional[dict] = None


# ── Excel endpoints ────────────────────────────────────────────────────────────

@router.post("/excel/sheets", response_model=SheetListResponse)
async def get_excel_sheets(file: UploadFile = File(...)):
    """
    Recibe un archivo Excel y retorna la lista de hojas disponibles.
    Usar antes del upload para que el usuario seleccione la hoja correcta.
    """
    content = await file.read()
    source_type = detect_source_type(file.filename or "")
    if source_type != "excel":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos Excel (.xlsx, .xls)",
        )

    try:
        reader = ExcelReader(content)
        sheets = reader.get_sheets()
        logger.info(f"Excel '{file.filename}' — {len(sheets)} hojas: {sheets}")
        return SheetListResponse(sheets=sheets)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error leyendo hojas de Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo leer el archivo Excel: {str(e)}",
        )


@router.post("/excel/headers", response_model=HeadersResponse)
async def get_excel_headers(file: UploadFile = File(...), sheet: Optional[str] = None):
    """
    Retorna los headers de una hoja específica de un Excel.
    Útil para el paso de auto-mapping de columnas.
    """
    content = await file.read()
    try:
        reader = ExcelReader(content)
        headers = reader.get_headers(sheet)
        return HeadersResponse(headers=headers, sheet=sheet)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error leyendo headers: {str(e)}",
        )


# ── Google Sheets endpoints ────────────────────────────────────────────────────

@router.post("/sheets/info", response_model=SheetListResponse)
async def get_google_sheets_info(request: SheetsInfoRequest):
    """
    Recibe una URL o ID de Google Sheets y retorna la lista de hojas (tabs).
    La hoja debe ser pública o compartida como 'Cualquiera con el enlace puede ver'.
    Requiere GOOGLE_SHEETS_API_KEY en .env.
    """
    settings = get_settings()
    api_key = settings.google_sheets_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "GOOGLE_SHEETS_API_KEY no está configurada en .env. "
                "Obtén una en https://console.cloud.google.com/ habilitando la API de Google Sheets."
            ),
        )

    try:
        spreadsheet_id = GoogleSheetsReader.extract_id(request.url_or_id)
        reader = GoogleSheetsReader(spreadsheet_id, api_key)
        sheets = reader.get_sheets()

        # Obtener título del spreadsheet para mostrar en UI
        meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
        meta_res = httpx.get(meta_url, params={"key": api_key, "fields": "properties.title"}, timeout=10)
        title = meta_res.json().get("properties", {}).get("title", "") if meta_res.status_code == 200 else ""

        logger.info(f"Google Sheets '{spreadsheet_id}' — {len(sheets)} hojas")
        return SheetListResponse(sheets=sheets, spreadsheet_id=spreadsheet_id, title=title)

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error accediendo a Google Sheets: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al conectar con Google Sheets: {str(e)}",
        )


@router.post("/sheets/headers", response_model=HeadersResponse)
async def get_google_sheets_headers(request: SheetsHeadersRequest):
    """
    Retorna los headers de una hoja específica de Google Sheets.
    Usar para el paso de auto-mapping antes de importar.
    """
    settings = get_settings()
    api_key = settings.google_sheets_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GOOGLE_SHEETS_API_KEY no está configurada en .env.",
        )

    try:
        reader = GoogleSheetsReader(request.spreadsheet_id, api_key)
        headers = reader.get_headers(request.sheet)
        return HeadersResponse(headers=headers, sheet=request.sheet)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error leyendo headers de Google Sheets: {str(e)}",
        )


@router.post("/sheets/import")
async def import_from_google_sheets(
    request: SheetsImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Importa datos directamente desde Google Sheets a la base de datos.
    Equivalente a subir un CSV pero tomando los datos de una hoja de cálculo.
    """
    settings = get_settings()
    api_key = settings.google_sheets_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GOOGLE_SHEETS_API_KEY no está configurada en .env.",
        )

    valid_types = {"ventas", "gastos", "inventario", "clientes"}
    if request.datasource_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"datasource_type debe ser uno de: {', '.join(valid_types)}",
        )

    try:
        reader = GoogleSheetsReader(request.spreadsheet_id, api_key)
        df = reader.read(sheet=request.sheet)

        # Apply column mapping if provided
        if request.column_mapping:
            df = df.rename(columns=request.column_mapping)

        uid = current_user.id
        # Parse + import by type con user_id
        if request.datasource_type == "ventas":
            df = parse_ventas_df(df)
            count, errors = import_ventas_rows(df, db, user_id=uid)
            key = "ventas_creadas"
        elif request.datasource_type == "gastos":
            df = parse_gastos_df(df)
            count, errors = import_gastos_rows(df, db, user_id=uid)
            key = "gastos_creados"
        elif request.datasource_type == "inventario":
            df = parse_inventario_df(df)
            creados, actualizados, errors = import_inventario_rows(df, db, user_id=uid)
            count = creados + actualizados
            key = "items_procesados"
        else:  # clientes
            df = parse_clientes_df(df)
            creados, actualizados, errors = import_clientes_rows(df, db, user_id=uid)
            count = creados + actualizados
            key = "clientes_procesados"

        # Obtener título del spreadsheet para source_name
        _gs_title = ""
        try:
            _meta = httpx.get(
                f"https://sheets.googleapis.com/v4/spreadsheets/{request.spreadsheet_id}",
                params={"key": api_key, "fields": "properties.title"}, timeout=5
            )
            if _meta.status_code == 200:
                _gs_title = _meta.json().get("properties", {}).get("title", "")
        except Exception:
            pass
        bump_import_version()
        save_and_watch(
            request.datasource_type, df, db,
            filename=f"gsheets_{request.spreadsheet_id}",
            source_type="google_sheets",
            sheet=request.sheet or "",
            spreadsheet_id=request.spreadsheet_id,
            source_name=_gs_title or request.spreadsheet_id,
            user_id=uid,
        )

        mensaje = f"Se importaron {count} registros desde Google Sheets"
        if errors:
            mensaje += f". {len(errors)} registros con errores"

        logger.info(f"[GSheets import] {request.datasource_type}: {count} registros (hoja: {request.sheet})")

        return {
            "status": "success",
            "message": mensaje,
            "data": {key: count, "errores": errors[:10] if errors else []},
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"[GSheets import] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error importando desde Google Sheets: {str(e)}",
        )
