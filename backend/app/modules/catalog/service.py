import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.catalog import Category, ComboComponent, HSNCode, Product, TaxRate, UnitOfMeasure
from app.modules.catalog.bulk_import import (
    BulkImportResult,
    RowResult,
    optional_bool,
    optional_number,
    optional_str,
    require_number,
    require_str,
)
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

    def bulk_import_products(self, organization_id: uuid.UUID, rows: list[tuple[int, dict]]) -> BulkImportResult:
        """Upserts one product per row, keyed on SKU. Each row is committed
        (or rolled back) on its own -- same reasoning as sync/service.py's
        per-sale commits -- so one bad row (unknown UOM code, a duplicate
        barcode, a non-numeric price) never discards the rows around it.
        """
        result = BulkImportResult()
        for row_number, raw in rows:
            try:
                result.results.append(self._import_product_row(organization_id, row_number, raw))
            except (ValidationError, ConflictError) as exc:
                self.db.rollback()
                result.results.append(RowResult(row_number, "error", raw.get("sku"), str(exc)))
            except Exception as exc:  # noqa: BLE001 -- a bad spreadsheet row must never abort the whole batch
                self.db.rollback()
                result.results.append(RowResult(row_number, "error", raw.get("sku"), f"Unexpected error: {exc}"))
        return result

    def _import_product_row(self, organization_id: uuid.UUID, row_number: int, raw: dict) -> RowResult:
        sku = require_str(raw, "sku")
        name = require_str(raw, "name")
        uom_code = require_str(raw, "uom_code")
        mrp = require_number(raw, "mrp")
        sale_price = require_number(raw, "sale_price")
        purchase_price = optional_number(raw, "purchase_price", default=0)
        reorder_level = optional_number(raw, "reorder_level", default=0)
        for label, value in (("mrp", mrp), ("sale_price", sale_price), ("purchase_price", purchase_price), ("reorder_level", reorder_level)):
            if value < 0:
                raise ValidationError(f"'{label}' cannot be negative")

        uom = self.uoms.get_by_code(organization_id, uom_code)
        if uom is None:
            raise ValidationError(f"Unknown UOM code '{uom_code}' -- create it under Catalog > Units of Measure first")

        hsn = None
        hsn_code = optional_str(raw, "hsn_code")
        if hsn_code:
            hsn = self.hsn.get_by_code(organization_id, hsn_code)
            if hsn is None:
                raise ValidationError(f"Unknown HSN code '{hsn_code}' -- create it under Catalog > HSN/SAC Codes first")

        category_id = None
        category_name = optional_str(raw, "category")
        if category_name:
            category = self.categories.get_by_name(organization_id, category_name)
            if category is None:
                category = self.create_category(organization_id, category_name, None)
            category_id = category.id

        fields = {
            "barcode": optional_str(raw, "barcode"),
            "name": name,
            "description": optional_str(raw, "description"),
            "category_id": category_id,
            "hsn_code_id": hsn.id if hsn else None,
            "uom_id": uom.id,
            "mrp": mrp,
            "sale_price": sale_price,
            "purchase_price": purchase_price,
            "reorder_level": reorder_level,
            "tracks_batches": optional_bool(raw, "tracks_batches", default=False),
            "tracks_serials": optional_bool(raw, "tracks_serials", default=False),
            "tracks_expiry": optional_bool(raw, "tracks_expiry", default=False),
        }

        existing = self.products.get_by_sku(organization_id, sku)
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            self.db.flush()
            self.db.commit()
            return RowResult(row_number, "updated", sku)

        product = Product(organization_id=organization_id, sku=sku, **fields)
        self.products.add(product)
        self.db.commit()
        return RowResult(row_number, "created", sku)

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
