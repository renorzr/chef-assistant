from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    EmbeddingReindexRequest,
    EmbeddingReindexResponse,
    EmbeddingAuditStatusResponse,
    EmbeddingRepairMissingRequest,
    EmbeddingRepairMissingResponse,
)
from services.recipe_service import reindex_recipe_embeddings
from services.embedding_audit_service import (
    get_audit_config,
    get_embedding_counts,
    get_last_result,
    repair_missing_embeddings,
)

router = APIRouter()


@router.post("/admin/embeddings/reindex", response_model=EmbeddingReindexResponse)
def reindex_embeddings_endpoint(payload: EmbeddingReindexRequest, db: Session = Depends(get_db)):
    result = reindex_recipe_embeddings(db, only_missing=payload.only_missing)
    if result.reindexed_count == 0 and result.failed_count > 0:
        raise HTTPException(status_code=503, detail=result.message)
    return result


@router.get("/admin/embeddings/audit", response_model=EmbeddingAuditStatusResponse)
def embedding_audit_status_endpoint(db: Session = Depends(get_db)):
    cfg = get_audit_config()
    total_recipes, missing_embeddings = get_embedding_counts(db)
    last = get_last_result()

    return EmbeddingAuditStatusResponse(
        enabled=cfg["enabled"],
        interval_seconds=cfg["interval_seconds"],
        batch_size=cfg["batch_size"],
        initial_delay_seconds=cfg["initial_delay_seconds"],
        total_recipes=total_recipes,
        missing_embeddings=missing_embeddings,
        last_run_at=last["last_run_at"],
        last_repaired_count=last["last_repaired_count"],
        last_failed_count=last["last_failed_count"],
    )


@router.post("/admin/embeddings/repair-missing", response_model=EmbeddingRepairMissingResponse)
def repair_missing_embeddings_endpoint(
    payload: EmbeddingRepairMissingRequest,
    db: Session = Depends(get_db),
):
    result = repair_missing_embeddings(db, batch_size=payload.batch_size)
    if result["repaired_count"] == 0 and result["failed_count"] > 0:
        raise HTTPException(
            status_code=503,
            detail="Repair failed. Check embedding provider configuration and availability.",
        )

    return EmbeddingRepairMissingResponse(
        attempted_count=result["attempted_count"],
        repaired_count=result["repaired_count"],
        failed_count=result["failed_count"],
        remaining_missing=result["remaining_missing"],
        message="Repair run completed.",
    )
