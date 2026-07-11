from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.organization import Branch
from app.models.rbac import User
from app.modules.organizations.schemas import BranchResponse

router = APIRouter(prefix="/api/v1/org", tags=["organizations"])


@router.get("/branches", response_model=list[BranchResponse])
def list_branches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = (
        select(Branch)
        .where(Branch.organization_id == user.organization_id, Branch.is_active.is_(True))
        .options(selectinload(Branch.warehouses))
    )
    return list(db.execute(stmt).scalars())
