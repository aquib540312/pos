import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.catalog import Category, ComboComponent, HSNCode, Product, TaxRate, UnitOfMeasure
from app.modules.catalog.repository import CategoryRepository, HSNRepository, ProductRepository, UOMRepository


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.categories = CategoryRepository(db)
        self.uoms = UOMRepository(db)
        self.hsn = HSNRepository(db)
        self.products = ProductRepository(db)

    def create_category(self, organization_id: uuid.UUID, name: str, parent_id: uuid.UUID | None) -> Category:
        return self.categories.add(Category(organization_id=organization_id, name=name, parent_id=parent_id))

    def create_uom(self, organization_id: uuid.UUID, code: str, name: str) -> UnitOfMeasure:
        return self.uoms.add(UnitOfMeasure(organization_id=organization_id, code=code, name=name))

    def create_hsn(
        self,
        organization_id: uuid.UUID,
        code: str,
        description: str | None,
        is_service: bool,
        rate_percent: float,
        cess_percent: float,
        effective_from: date,
    ) -> HSNCode:
        hsn = self.hsn.add(HSNCode(organization_id=organization_id, code=code, description=description, is_service=is_service))
        self.hsn.add_tax_rate(
            TaxRate(
                organization_id=organization_id,
                hsn_code_id=hsn.id,
                rate_percent=rate_percent,
                cess_percent=cess_percent,
                effective_from=effective_from,
            )
        )
        return hsn

    def hsn_current_rate(self, hsn_code_id: uuid.UUID) -> float | None:
        rate = self.hsn.get_effective_tax_rate(hsn_code_id, date.today())
        return float(rate.rate_percent) if rate else None

    def create_product(self, organization_id: uuid.UUID, **fields) -> Product:
        """A combo product bills as a single line at its own price/HSN --
        exactly like a normal product -- but has no stock of its own. See
        sales/service.py: selling/returning a combo line decrements/
        restores each *component's* stock instead, scaled by
        `component.quantity`. Nesting combos inside combos is rejected to
        keep that stock math a single level deep."""
        if self.products.get_by_sku(organization_id, fields["sku"]) is not None:
            raise ConflictError(f"SKU '{fields['sku']}' already exists")

        combo_components = fields.pop("combo_components", []) or []
        is_combo = fields.get("is_combo", False)
        if is_combo and not combo_components:
            raise ValidationError("A combo product must have at least one component")
        if not is_combo and combo_components:
            raise ValidationError("combo_components can only be set when is_combo is true")

        product = Product(organization_id=organization_id, **fields)
        self.products.add(product)

        for comp in combo_components:
            component = self.products.get(comp["component_product_id"])
            if component is None:
                raise NotFoundError(f"Component product {comp['component_product_id']} not found")
            if component.is_combo:
                raise ValidationError("A combo product cannot contain another combo product as a component")
            self.db.add(
                ComboComponent(
                    combo_product_id=product.id,
                    component_product_id=component.id,
                    quantity=comp["quantity"],
                )
            )
        self.db.flush()
        return product

    def get_product_or_404(self, product_id: uuid.UUID) -> Product:
        product = self.products.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def search_products(self, organization_id: uuid.UUID, search: str | None) -> list[Product]:
        return self.products.list(organization_id, search=search)

    def find_by_barcode(self, organization_id: uuid.UUID, barcode: str) -> Product:
        product = self.products.get_by_barcode(organization_id, barcode)
        if product is None:
            raise NotFoundError(f"No product with barcode '{barcode}'")
        return product
