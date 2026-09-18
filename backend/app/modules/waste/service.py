import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.waste import WasteEntry


class WasteService:
    def __init__(self, db: Session):
        self.db = db

    def create_waste(self, organization_id: uuid.UUID, user_id: uuid.UUID,
                     product_id: uuid.UUID, quantity: float, unit_cost: float,
                     reason: str, notes: str | None = None) -> WasteEntry:
        total_cost = quantity * unit_cost
        entry = WasteEntry(
            organization_id=organization_id,
            product_id=product_id,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reason=reason,
            notes=notes,
            recorded_by=user_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_waste(self, organization_id: uuid.UUID) -> list[WasteEntry]:
        return self.db.query(WasteEntry).filter(WasteEntry.organization_id == organization_id).order_by(WasteEntry.created_at.desc()).all()
