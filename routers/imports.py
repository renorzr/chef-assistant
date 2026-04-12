from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    RecipeImportCreateRequest,
    RecipeImportStatusResponse,
    RecipeImportResumeCookiesRequest,
    RecipeImportSubmitHtmlRequest,
    RecipeImportPreviewResponse,
    RecipeImportCommitResponse,
    XiachufangRecommendedImportCreateRequest,
    XiachufangRecommendedRunResponse,
    XiachufangRecommendedRunItemsResponse,
)
from services.import_service import (
    create_import_job,
    get_import_job_status,
    resume_import_with_cookies,
    submit_import_html,
    get_import_preview,
    commit_import_job,
    create_recommended_import_run,
    get_recommended_import_run_status,
    list_recommended_import_run_items,
    resume_recommended_import_with_cookies,
    submit_recommended_homepage_html,
)

router = APIRouter()


@router.post("/recipes/import", response_model=RecipeImportStatusResponse, status_code=201)
def create_import_job_endpoint(payload: RecipeImportCreateRequest, db: Session = Depends(get_db)):
    try:
        return create_import_job(db, payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/recipes/import/{job_id}", response_model=RecipeImportStatusResponse)
def get_import_job_status_endpoint(job_id: int, db: Session = Depends(get_db)):
    try:
        return get_import_job_status(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/recipes/import/{job_id}/resume-with-cookies", response_model=RecipeImportStatusResponse)
def resume_import_with_cookies_endpoint(
    job_id: int,
    payload: RecipeImportResumeCookiesRequest,
    db: Session = Depends(get_db),
):
    try:
        return resume_import_with_cookies(db, job_id, payload.cookie)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/recipes/import/{job_id}/submit-html", response_model=RecipeImportStatusResponse)
def submit_import_html_endpoint(
    job_id: int,
    payload: RecipeImportSubmitHtmlRequest,
    db: Session = Depends(get_db),
):
    try:
        return submit_import_html(db, job_id, payload.html)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/recipes/import/{job_id}/preview", response_model=RecipeImportPreviewResponse)
def get_import_preview_endpoint(job_id: int, db: Session = Depends(get_db)):
    try:
        return get_import_preview(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/recipes/import/{job_id}/commit", response_model=RecipeImportCommitResponse)
def commit_import_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    try:
        return commit_import_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/recipes/import/xiachufang/recommended",
    response_model=XiachufangRecommendedRunResponse,
    status_code=201,
)
def create_recommended_import_run_endpoint(
    payload: XiachufangRecommendedImportCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return create_recommended_import_run(
            db=db,
            homepage_url=payload.homepage_url,
            max_links=payload.max_links,
            auto_commit=payload.auto_commit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/recipes/import/xiachufang/recommended/{run_id}",
    response_model=XiachufangRecommendedRunResponse,
)
def get_recommended_import_run_status_endpoint(run_id: int, db: Session = Depends(get_db)):
    try:
        return get_recommended_import_run_status(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/recipes/import/xiachufang/recommended/{run_id}/items",
    response_model=XiachufangRecommendedRunItemsResponse,
)
def list_recommended_import_run_items_endpoint(run_id: int, db: Session = Depends(get_db)):
    try:
        return list_recommended_import_run_items(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/recipes/import/xiachufang/recommended/{run_id}/resume-with-cookies",
    response_model=XiachufangRecommendedRunResponse,
)
def resume_recommended_import_with_cookies_endpoint(
    run_id: int,
    payload: RecipeImportResumeCookiesRequest,
    db: Session = Depends(get_db),
):
    try:
        return resume_recommended_import_with_cookies(db, run_id, payload.cookie)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/recipes/import/xiachufang/recommended/{run_id}/submit-html",
    response_model=XiachufangRecommendedRunResponse,
)
def submit_recommended_homepage_html_endpoint(
    run_id: int,
    payload: RecipeImportSubmitHtmlRequest,
    db: Session = Depends(get_db),
):
    try:
        return submit_recommended_homepage_html(db, run_id, payload.html)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
