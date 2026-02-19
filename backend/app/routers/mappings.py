"""
Lumina_Ant - Router de Mappings
Endpoints para auto-mapeo, guardado y consulta de mapeos de columnas CSV
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database import get_db
from app.models.models import ColumnMapping
from app.schemas.schemas import (
    AutoMapRequest, AutoMapResponse, ColumnMappingSuggestion,
    SaveMappingRequest, MessageResponse,
)
from app.services.mapping_service import (
    auto_map, detect_structure_change, DATASOURCE_COLUMNS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


@router.post("/auto-map", response_model=AutoMapResponse)
def auto_map_columns(request: AutoMapRequest, db: Session = Depends(get_db)):
    """
    Recibe headers de un CSV + tipo de datasource y retorna sugerencias de mapeo.
    Consulta mappings guardados en DB para mejorar las sugerencias.
    """
    # Cargar mappings guardados
    saved_rows = db.query(ColumnMapping).filter(
        ColumnMapping.user_id == request.user_id,
        ColumnMapping.datasource_type == request.datasource_type,
    ).all()
    saved_mappings = {row.original_column: row.mapped_column for row in saved_rows}
    has_saved = len(saved_mappings) > 0

    # Detectar cambio de estructura
    structure_changed = detect_structure_change(request.headers, saved_mappings)

    # Ejecutar auto-mapeo
    suggestions = auto_map(request.headers, request.datasource_type, saved_mappings)

    # Determinar columnas requeridas sin mapear
    target_info = DATASOURCE_COLUMNS[request.datasource_type]
    required_targets = {c["name"] for c in target_info if c["required"]}
    high_conf_targets = {
        s["target_column"] for s in suggestions
        if s["target_column"] and s["confidence"] >= 0.6
    }
    unmapped_required = sorted(required_targets - high_conf_targets)
    all_mapped = len(unmapped_required) == 0

    logger.info(
        f"Auto-map {request.datasource_type}: {len(suggestions)} headers, "
        f"all_mapped={all_mapped}, saved={has_saved}, changed={structure_changed}"
    )

    return AutoMapResponse(
        mappings=[ColumnMappingSuggestion(**s) for s in suggestions],
        all_mapped=all_mapped,
        unmapped_required=unmapped_required,
        target_columns=target_info,
        has_saved_mappings=has_saved,
        structure_changed=structure_changed,
    )


@router.post("/{datasource_type}", response_model=MessageResponse)
def save_mappings(
    datasource_type: str,
    request: SaveMappingRequest,
    db: Session = Depends(get_db),
):
    """
    Guarda mapeos confirmados. Reemplaza todos los mapeos previos
    para este usuario+datasource.
    """
    # Eliminar mapeos anteriores
    db.query(ColumnMapping).filter(
        ColumnMapping.user_id == request.user_id,
        ColumnMapping.datasource_type == datasource_type,
    ).delete()

    # Insertar nuevos
    for original, mapped in request.mappings.items():
        if mapped:  # Solo guardar los que tienen destino
            db.add(ColumnMapping(
                user_id=request.user_id,
                datasource_type=datasource_type,
                original_column=original,
                mapped_column=mapped,
            ))

    db.commit()
    logger.info(f"Guardados {len(request.mappings)} mappings para {datasource_type} (user={request.user_id})")

    return MessageResponse(
        status="success",
        message=f"Se guardaron {len(request.mappings)} mapeos para {datasource_type}",
    )
