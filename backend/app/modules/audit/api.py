from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.audit.schemas import AuditLogResponse
from app.modules.audit.service import list_audit_logs

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.ORG_MANAGE))):
    return list_audit_logs(db, user.organization_id)
