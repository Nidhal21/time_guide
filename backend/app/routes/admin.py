from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.db_config import get_db
from app.services.admin_import_service import get_admin_dashboard_summary, process_uploads
from app.services.auth_service import get_admin_user


router = APIRouter()


@router.get("/admin/imports/status")
async def admin_import_status(
    db: Session = Depends(get_db),
    _admin_user=Depends(get_admin_user),
):
    return get_admin_dashboard_summary(db)


@router.post("/admin/imports/upload")
async def admin_import_upload(
    student_s1: Optional[UploadFile] = File(None),
    student_s2: Optional[UploadFile] = File(None),
    rooms_s1: Optional[UploadFile] = File(None),
    rooms_s2: Optional[UploadFile] = File(None),
    teachers_s1: Optional[UploadFile] = File(None),
    teachers_s2: Optional[UploadFile] = File(None),
    calendar: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _admin_user=Depends(get_admin_user),
):
    uploads = {
        "student_s1": student_s1,
        "student_s2": student_s2,
        "rooms_s1": rooms_s1,
        "rooms_s2": rooms_s2,
        "teachers_s1": teachers_s1,
        "teachers_s2": teachers_s2,
        "calendar": calendar,
    }

    try:
        return process_uploads(db, uploads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
