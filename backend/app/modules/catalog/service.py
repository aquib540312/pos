import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.catalog import Category, ComboComponent, HSNCode, Product, ProductAlias, TaxRate, UnitOfMeasure
from app.models.organization import Warehouse
from app.modules.catalog.bulk_import import (
    BulkImportResult,
    RowResult,
    optional_bool,
    optional_number,
    optional_str,
    require_number,
    require_str,
)
from app.modules.catalog.labels import InvalidLabelDataError, generate_ean13
from app.modules.catalog.repository import CategoryRepository, HSNRepository, ProductRepository, UOMRepository
from app.modules.inventory.service import InventoryService


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

    def _assign_product_aliases(self, product: Product, aliases: list[str]) -> None:
        """Replace the product's search aliases. Aliases are normalized
        (stripped, deduped, casefolded) and rejected when they collide with
        another product's SKU/barcode/alias in the same organization."""
        for existing in product.aliases:
            self.db.delete(existing)
        product.aliases = []
        seen: set[str] = set()
        for raw in aliases:
            alias = raw.strip()
            if not alias:
                continue
            alias_key = alias.casefold()
            if alias_key in seen:
                continue
            seen.add(alias_key)
            if self.products.get_by_sku(organization_id := product.organization_id, alias) is not None:
                raise ValidationError(f"Alias '{alias}' collides with an existing SKU")
            if self.products.get_by_barcode(organization_id, alias) is not None:
                raise ValidationError(f"Alias '{alias}' collides with an existing barcode")
            if self.products.get_by_alias(organization_id, alias, exclude_product_id=product.id) is not None:
                raise ValidationError(f"Alias '{alias}' is already used by another product")
            self.db.add(ProductAlias(organization_id=organization_id, product_id=product.id, alias=alias))

    def _derive_gst_exclusive_price(self, hsn_code_id: uuid.UUID | None, sale_price: float) -> float:
        """Convert a GST-inclusive sale price to the GST-exclusive value that
        is actually stored/billed, using the HSN's current effective rate."""
        rate = self.hsn_current_rate(hsn_code_id) if hsn_code_id else None
        if rate is None or rate <= 0:
            return sale_price
        return round(sale_price * 100 / (100 + rate), 2)

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

        aliases = fields.pop("aliases", []) or []
        generate_barcode = fields.pop("generate_barcode", False)
        if generate_barcode and not fields.get("barcode"):
            base = f"890{str(uuid.uuid4().int)[:9]}"
            try:
                fields["barcode"] = generate_ean13(base)
            except InvalidLabelDataError:  # pragma: no cover -- base is always 12 digits
                pass

        initial_stock_qty = fields.pop("initial_stock_qty", 0) or 0
        warehouse_id = fields.pop("warehouse_id", None)
        if fields.get("prices_gst_inclusive") and fields.get("sale_price"):
            fields["sale_price"] = self._derive_gst_exclusive_price(fields.get("hsn_code_id"), fields["sale_price"])

        parent_id = fields.get("parent_product_id")
        if parent_id is not None:
            parent = self.products.get(parent_id)
            if parent is None:
                raise NotFoundError(f"Parent product {parent_id} not found")
            if parent.organization_id != organization_id:
                raise NotFoundError(f"Parent product {parent_id} not found")
            if not fields.get("variant_label"):
                raise ValidationError("A variant product must have a variant_label (e.g. 'M', 'Red')")

        product = Product(organization_id=organization_id, **fields)
        self.products.add(product)
        self._assign_product_aliases(product, aliases)

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

        if initial_stock_qty > 0:
            warehouse = self.db.get(Warehouse, warehouse_id) if warehouse_id else None
            if warehouse is None:
                raise ValidationError("Opening stock requires a valid warehouse_id")
            InventoryService(self.db).receive(
                organization_id, warehouse.id, product.id, None, initial_stock_qty,
                "adjustment_in", "product_create", product.id,
                notes="Opening stock on product creation",
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
        wholesale_price = optional_number(raw, "wholesale_price", default=0)
        reorder_level = optional_number(raw, "reorder_level", default=0)
        for label, value in (
            ("mrp", mrp), ("sale_price", sale_price), ("purchase_price", purchase_price),
            ("wholesale_price", wholesale_price), ("reorder_level", reorder_level),
        ):
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

        aliases = []
        raw_aliases = optional_str(raw, "aliases")
        if raw_aliases:
            aliases = [a.strip() for a in raw_aliases.split(",") if a.strip()]

        fields = {
            "barcode": optional_str(raw, "barcode"),
            "name": name,
            "name_arabic": optional_str(raw, "name_arabic"),
            "brand": optional_str(raw, "brand"),
            "description": optional_str(raw, "description"),
            "category_id": category_id,
            "hsn_code_id": hsn.id if hsn else None,
            "uom_id": uom.id,
            "mrp": mrp,
            "sale_price": sale_price,
            "wholesale_price": wholesale_price,
            "restaurant_price": optional_number(raw, "restaurant_price", default=0),
            "vip_price": optional_number(raw, "vip_price", default=0),
            "purchase_price": purchase_price,
            "cost_per_kg": optional_number(raw, "cost_per_kg", default=0),
            "selling_price_per_kg": optional_number(raw, "selling_price_per_kg", default=0),
            "minimum_selling_quantity": optional_number(raw, "minimum_selling_quantity", default=0),
            "reorder_level": reorder_level,
            "tracks_batches": optional_bool(raw, "tracks_batches", default=False),
            "tracks_serials": optional_bool(raw, "tracks_serials", default=False),
            "tracks_expiry": optional_bool(raw, "tracks_expiry", default=False),
            "is_weighted": optional_bool(raw, "is_weighted", default=False),
            "loyalty_exempt": optional_bool(raw, "loyalty_exempt", default=False),
            "beef_cut": optional_str(raw, "beef_cut"),
            "fresh_frozen": optional_str(raw, "fresh_frozen"),
            "local_imported": optional_str(raw, "local_imported"),
            "country_of_origin": optional_str(raw, "country_of_origin"),
            "storage_location": optional_str(raw, "storage_location"),
        }

        existing = self.products.get_by_sku(organization_id, sku)
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            if aliases:
                self._assign_product_aliases(existing, aliases)
            self.db.flush()
            self.db.commit()
            return RowResult(row_number, "updated", sku)

        product = Product(organization_id=organization_id, sku=sku, **fields)
        self.products.add(product)
        if aliases:
            self._assign_product_aliases(product, aliases)
        self.db.commit()
        return RowResult(row_number, "created", sku)

    def get_product_or_404(self, product_id: uuid.UUID) -> Product:
        product = self.products.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def update_product(self, organization_id: uuid.UUID, product_id: uuid.UUID, fields: dict) -> Product:
        """Partial edit of a product. `None` values in `fields` mean "leave
        unchanged" -- nullable values are cleared via the explicit
        remove_barcode/remove_description flags instead (see schemas)."""
        product = self.get_product_or_404(product_id)
        if product.organization_id != organization_id:
            raise NotFoundError(f"Product {product_id} not found")

        sku = fields.get("sku")
        if sku is not None and sku != product.sku:
            existing = self.products.get_by_sku(organization_id, sku)
            if existing is not None and existing.id != product.id:
                raise ConflictError(f"SKU '{sku}' already exists")
            product.sku = sku

        barcode = fields.get("barcode")
        if barcode is not None and barcode != product.barcode:
            existing = self.products.get_by_barcode(organization_id, barcode)
            if existing is not None and existing.id != product.id:
                raise ConflictError(f"Barcode '{barcode}' already exists")
            product.barcode = barcode

        for key in ("name", "name_arabic", "description", "category_id", "hsn_code_id", "uom_id", "supplier_id",
                    "mrp", "sale_price", "purchase_price", "reorder_level", "is_active",
                    "brand", "wholesale_price", "restaurant_price", "vip_price",
                    "cost_per_kg", "selling_price_per_kg", "minimum_selling_quantity",
                    "low_stock_notify", "is_weighted",
                    "loyalty_exempt", "prices_gst_inclusive", "parent_product_id", "variant_label",
                    "beef_cut", "fresh_frozen", "local_imported", "country_of_origin", "storage_location"):
            if fields.get(key) is not None:
                setattr(product, key, fields[key])

        if fields.get("prices_gst_inclusive") and fields.get("sale_price") is not None:
            product.sale_price = self._derive_gst_exclusive_price(product.hsn_code_id, product.sale_price)
        if "aliases" in fields and fields["aliases"] is not None:
            self._assign_product_aliases(product, fields["aliases"])
        if fields.get("remove_barcode"):
            product.barcode = None
        if fields.get("remove_description"):
            product.description = None
        if fields.get("remove_brand"):
            product.brand = None
        if fields.get("remove_variant"):
            product.parent_product_id = None
            product.variant_label = None
        self.db.flush()
        return product

    def deactivate_product(self, organization_id: uuid.UUID, product_id: uuid.UUID) -> Product:
        """Soft-delete: flips is_active off so the product disappears from
        searchable/billable lists but historical invoices keep resolving.
        Public-combination removal is handled by the caller wiping the
        forward components (see create_* for the combo invariant)."""
        product = self.get_product_or_404(product_id)
        if product.organization_id != organization_id:
            raise NotFoundError(f"Product {product_id} not found")
        product.is_active = False
        self.db.flush()
        return product

    def update_category(self, organization_id: uuid.UUID, category_id: uuid.UUID, fields: dict) -> Category:
        category = self.db.get(Category, category_id)
        if category is None or category.organization_id != organization_id:
            raise NotFoundError(f"Category {category_id} not found")
        if fields.get("name") is not None:
            category.name = fields["name"]
        if fields.get("remove_parent"):
            category.parent_id = None
        elif fields.get("parent_id") is not None:
            category.parent_id = fields["parent_id"]
        self.db.flush()
        return category

    def update_uom(self, organization_id: uuid.UUID, uom_id: uuid.UUID, fields: dict) -> UnitOfMeasure:
        uom = self.db.get(UnitOfMeasure, uom_id)
        if uom is None or uom.organization_id != organization_id:
            raise NotFoundError(f"Unit of measure {uom_id} not found")
        code = fields.get("code")
        if code is not None and code != uom.code:
            existing = self.uoms.get_by_code(organization_id, code)
            if existing is not None and existing.id != uom.id:
                raise ConflictError(f"UOM code '{code}' already exists")
            uom.code = code
        if fields.get("name") is not None:
            uom.name = fields["name"]
        self.db.flush()
        return uom

    def update_hsn(
        self, organization_id: uuid.UUID, hsn_id: uuid.UUID, fields: dict
    ) -> HSNCode:
        """Edit an HSN/SAC code. A change to rate/cess creates a *new*
        versioned TaxRate row (effective today) rather than mutating the old
        one, so historical invoices keep the rate they were billed at."""
        hsn = self.hsn.get(hsn_id)
        if hsn is None or hsn.organization_id != organization_id:
            raise NotFoundError(f"HSN/SAC code {hsn_id} not found")

        code = fields.get("code")
        if code is not None and code != hsn.code:
            existing = self.hsn.get_by_code(organization_id, code)
            if existing is not None and existing.id != hsn.id:
                raise ConflictError(f"HSN code '{code}' already exists")
            hsn.code = code
        if fields.get("description") is not None:
            hsn.description = fields["description"]
        if fields.get("remove_description"):
            hsn.description = None
        if fields.get("is_service") is not None:
            hsn.is_service = fields["is_service"]

        rate = fields.get("rate_percent")
        if rate is not None:
            effective_from = fields.get("effective_from") or date.today()
            # Close out the currently-effective rate so historical invoices
            # keep theirs, but lookups from `effective_from` resolve to the
            # new one.
            current = self.hsn.get_effective_tax_rate(hsn.id, effective_from)
            if current is not None and current.effective_to is None:
                current.effective_to = effective_from - timedelta(days=1)
            self.hsn.add_tax_rate(
                TaxRate(
                    organization_id=organization_id,
                    hsn_code_id=hsn.id,
                    rate_percent=rate,
                    cess_percent=fields.get("cess_percent") or 0,
                    effective_from=effective_from,
                )
            )
        self.db.flush()
        return hsn

    def search_products(self, organization_id: uuid.UUID, search: str | None) -> list[Product]:
        return self.products.list(organization_id, search=search)

    def find_by_barcode(self, organization_id: uuid.UUID, barcode: str) -> Product:
        product = self.products.get_by_barcode(organization_id, barcode)
        if product is None:
            raise NotFoundError(f"No product with barcode '{barcode}'")
        return product
