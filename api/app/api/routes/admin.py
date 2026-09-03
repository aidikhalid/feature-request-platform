from fastapi import APIRouter, Depends

from app.api.presenters import request_detail
from app.core.deps import AdminUser, DbSession, require_admin
from app.schemas import FeatureRequestDetail, MergeIn, OfficialResponseIn, StatsOut, StatusUpdateIn
from app.services import admin_service, merge_service, stats_service

# Every route in this router is admin-only. Declaring the dependency once at the router
# level means a new endpoint added here is protected by default rather than by memory.
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.patch("/requests/{request_id}/status", response_model=FeatureRequestDetail)
def set_status(request_id: int, payload: StatusUpdateIn, db: DbSession, admin: AdminUser):
    request = admin_service.set_status(db, request_id, payload.status)
    return request_detail(db, request, admin)


@router.put("/requests/{request_id}/response", response_model=FeatureRequestDetail)
def set_official_response(
    request_id: int, payload: OfficialResponseIn, db: DbSession, admin: AdminUser
):
    request = admin_service.set_official_response(db, request_id, admin, payload.body)
    return request_detail(db, request, admin)


@router.post("/requests/{request_id}/merge", response_model=FeatureRequestDetail)
def merge(request_id: int, payload: MergeIn, db: DbSession, admin: AdminUser):
    """Merge `request_id` (the duplicate) into `target_id` (the survivor)."""
    target = merge_service.merge_requests(db, request_id, payload.target_id)
    return request_detail(db, target, admin)


@router.get("/stats", response_model=StatsOut)
def stats(db: DbSession) -> StatsOut:
    return stats_service.get_stats(db)
