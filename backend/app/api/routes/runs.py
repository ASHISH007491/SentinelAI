"""Runs API: create, list, upload artefacts, execute, and fetch detailed results.

All endpoints require auth and are scoped to the calling user's runs.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.artefact import Artefact
from app.models.run import Run
from app.models.user import User
from app.schemas.artefact import ArtefactRead
from app.schemas.run import RunCreate, RunDetail, RunRead
from app.services import orchestration, storage

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_owned_run(run_id: int, db: Session, user: User) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("", response_model=RunRead, status_code=201)
def create_run(
    payload: RunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Run:
    run = Run(owner_id=user.id, workflow=payload.workflow, architecture=payload.architecture)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("", response_model=list[RunRead])
def list_runs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Run]:
    return list(db.scalars(select(Run).where(Run.owner_id == user.id)))


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Run:
    return _get_owned_run(run_id, db, user)


@router.post("/{run_id}/artefacts", response_model=ArtefactRead, status_code=201)
def upload_artefact(
    run_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Artefact:
    run = _get_owned_run(run_id, db, user)
    data = file.file.read()
    path, size = storage.save_bytes(run.id, file.filename or "upload.bin", data)
    artefact = Artefact(
        run_id=run.id,
        filename=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        storage_path=path,
        size_bytes=size,
    )
    db.add(artefact)
    db.commit()
    db.refresh(artefact)
    return artefact


@router.post("/{run_id}/execute", response_model=RunDetail)
def execute_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Run:
    run = _get_owned_run(run_id, db, user)
    if not run.artefacts:
        raise HTTPException(status_code=400, detail="Upload at least one artefact first")
    return orchestration.execute_run(db, run)
