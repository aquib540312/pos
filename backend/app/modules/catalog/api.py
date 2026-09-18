import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.catalog import Product
from app.models.rbac import User
from app.modules.catalog.bulk_import import generate_product_import_template, parse_product_workbook
from app.modules.catalog.labels import (
    InvalidLabelDataError,
    generate_barcode_png,
    generate_label_sheet_png,
    generate_qr_png,
)
from app.modules.catalog.schemas import (
    BulkImportResponse,
    BulkImportRowResult,
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    ComboComponentResponse,
    HSNCreateRequest,
    HSNResponse,
    HSNUpdateRequest,
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
    UOMCreateRequest,
    UOMResponse,
    UOMUpdateRequest,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


def _to_product_response(service: CatalogService, product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        sku=product.sku,
        barcode=product.barcode,
        name=product.name,
        name_arabic=product.name_arabic,
        brand=product.brand,
        category_id=product.category_id,
        category_name=product.category.name if product.category else None,
        uom_id=product.uom_id,
        hsn_code_id=product.hsn_code_id,
        supplier_id=product.supplier_id,
        mrp=product.mrp,
        sale_price=product.sale_price,
        wholesale_price=product.wholesale_price,
        restaurant_price=product.restaurant_price,
        vip_price=product.vip_price,
        purchase_price=product.purchase_price,
        cost_per_kg=product.cost_per_kg,
        selling_price_per_kg=product.selling_price_per_kg,
        minimum_selling_quantity=product.minimum_selling_quantity,
        tax_rate_percent=service.hsn_current_rate(product.hsn_code_id) if product.hsn_code_id else None,
        tracks_batches=product.tracks_batches,
        tracks_serials=product.tracks_serials,
        tracks_expiry=product.tracks_expiry,
        is_weighted=product.is_weighted,
        low_stock_notify=product.low_stock_notify,
        reorder_level=product.reorder_level,
        is_active=product.is_active,
        is_combo=product.is_combo,
        combo_components=[
            ComboComponentResponse(
                component_product_id=c.component_product_id,
                component_product_name=c.component_product.name,
                quantity=c.quantity,
            )
            for c in product.combo_components
        ],
        prices_gst_inclusive=product.prices_gst_inclusive,
        loyalty_exempt=product.loyalty_exempt,
        parent_product_id=product.parent_product_id,
        variant_label=product.variant_label,
        image_path=product.image_path,
        aliases=[a.alias for a in product.aliases],
        beef_cut=product.beef_cut,
        fresh_frozen=product.fresh_frozen,
        local_imported=product.local_imported,
        country_of_origin=product.country_of_origin,
        storage_location=product.storage_location,
    )


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))):
    return CatalogService(db).categories.list(user.organization_id)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    category = CatalogService(db).create_category(user.organization_id, payload.name, payload.parent_id)
    db.commit()
    return category


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    service = CatalogService(db)
    try:
        category = service.update_category(user.organization_id, category_id, payload.model_dump())
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return category


@router.get("/uom", response_model=list[UOMResponse])
def list_uom(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))):
    return CatalogService(db).uoms.list(user.organization_id)


@router.post("/uom", response_model=UOMResponse, status_code=status.HTTP_201_CREATED)
def create_uom(
    payload: UOMCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    uom = CatalogService(db).create_uom(user.organization_id, payload.code, payload.name)
    db.commit()
    return uom


@router.patch("/uom/{uom_id}", response_model=UOMResponse)
def update_uom(
    uom_id: uuid.UUID,
    payload: UOMUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    service = CatalogService(db)
    try:
        uom = service.update_uom(user.organization_id, uom_id, payload.model_dump())
        db.commit()
    except (NotFoundError, ConflictError) as exc:
        db.rollback()
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(code, str(exc)) from exc
    return uom


@router.get("/hsn", response_model=list[HSNResponse])
def list_hsn(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))):
    service = CatalogService(db)
    hsn_codes = service.hsn.list(user.organization_id)
    return [
        HSNResponse(
            id=h.id,
            code=h.code,
            description=h.description,
            is_service=h.is_service,
            current_rate_percent=service.hsn_current_rate(h.id),
        )
        for h in hsn_codes
    ]


@router.post("/hsn", response_model=HSNResponse, status_code=status.HTTP_201_CREATED)
def create_hsn(
    payload: HSNCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    service = CatalogService(db)
    hsn = service.create_hsn(
        user.organization_id,
        payload.code,
        payload.description,
        payload.is_service,
        payload.rate_percent,
        payload.cess_percent,
        payload.effective_from,
    )
    db.commit()
    return HSNResponse(
        id=hsn.id,
        code=hsn.code,
        description=hsn.description,
        is_service=hsn.is_service,
        current_rate_percent=payload.rate_percent,
    )


@router.patch("/hsn/{hsn_id}", response_model=HSNResponse)
def update_hsn(
    hsn_id: uuid.UUID,
    payload: HSNUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    service = CatalogService(db)
    try:
        hsn = service.update_hsn(user.organization_id, hsn_id, payload.model_dump())
        db.commit()
    except (NotFoundError, ConflictError) as exc:
        db.rollback()
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(code, str(exc)) from exc
    return HSNResponse(
        id=hsn.id,
        code=hsn.code,
        description=hsn.description,
        is_service=hsn.is_service,
        current_rate_percent=service.hsn_current_rate(hsn.id),
    )


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_VIEW)),
):
    service = CatalogService(db)
    return [_to_product_response(service, p) for p in service.search_products(user.organization_id, search)]


@router.get("/products/barcode/{barcode}", response_model=ProductResponse)
def get_product_by_barcode(
    barcode: str, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))
):
    service = CatalogService(db)
    try:
        return _to_product_response(service, service.find_by_barcode(user.organization_id, barcode))
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))
):
    service = CatalogService(db)
    try:
        return _to_product_response(service, service.get_product_or_404(product_id))
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    service = CatalogService(db)
    try:
        product = service.create_product(user.organization_id, **payload.model_dump())
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (ValidationError, NotFoundError) as exc:
        db.rollback()
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, str(exc)) from exc
    return _to_product_response(service, product)


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    service = CatalogService(db)
    try:
        product = service.update_product(user.organization_id, product_id, payload.model_dump())
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _to_product_response(service, product)


@router.patch("/products/{product_id}/deactivate", response_model=ProductResponse)
def deactivate_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    """Soft-delete a product: hidden from search and the billing screen,
    but historical invoices keep resolving. Combo components that reference
    it are unlinked so a deactivated product never leaks back into a cart."""
    service = CatalogService(db)
    try:
        product = service.deactivate_product(user.organization_id, product_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _to_product_response(service, product)


@router.get("/products/bulk-import/template")
def download_bulk_import_template(user: User = Depends(require_permission(Perm.CATALOG_MANAGE))):
    content = generate_product_import_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=product-import-template.xlsx"},
    )


@router.post("/products/bulk-import", response_model=BulkImportResponse)
async def bulk_import_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    content = await file.read()
    try:
        rows = parse_product_workbook(content)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The uploaded file has no product rows")

    result = CatalogService(db).bulk_import_products(user.organization_id, rows)
    return BulkImportResponse(
        total=len(result.results),
        created=result.created,
        updated=result.updated,
        failed=result.failed,
        rows=[BulkImportRowResult(row=r.row_number, sku=r.sku, status=r.status, error=r.error) for r in result.results],
    )


@router.get("/products/{product_id}/barcode.png")
def get_product_barcode_image(
    product_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))
):
    service = CatalogService(db)
    try:
        product = service.get_product_or_404(product_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    try:
        png = generate_barcode_png(product.barcode or product.sku)
    except InvalidLabelDataError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return Response(content=png, media_type="image/png")


@router.get("/products/{product_id}/qr.png")
def get_product_qr_image(
    product_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))
):
    service = CatalogService(db)
    try:
        product = service.get_product_or_404(product_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    payload = f"SKU:{product.sku}|{product.name}|MRP:{product.mrp}"
    return Response(content=generate_qr_png(payload), media_type="image/png")


@router.get("/products/{product_id}/label-sheet.png")
def get_product_label_sheet(
    product_id: uuid.UUID,
    copies: int = Query(default=1, ge=1, le=100),
    columns: int = Query(default=3, ge=1, le=6),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_VIEW)),
):
    service = CatalogService(db)
    try:
        product = service.get_product_or_404(product_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    try:
        png = generate_label_sheet_png(product.barcode or product.sku, product.name, float(product.mrp), copies, columns)
    except InvalidLabelDataError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return Response(content=png, media_type="image/png")


@router.post("/products/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    """Store a product photo under backend/uploads/ and point the product at
    it. Served back via GET /catalog/products/{id}/image.png."""
    service = CatalogService(db)
    try:
        product = service.get_product_or_404(product_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Image must be PNG, JPG/JPEG or WebP")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image must be 2 MB or smaller")

    upload_dir = get_settings().product_image_dir
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{product.id}{ext}"
    with open(os.path.join(upload_dir, filename), "wb") as fh:
        fh.write(content)

    product.image_path = filename
    db.commit()
    return _to_product_response(service, product)


@router.get("/products/{product_id}/image.png")
def get_product_image(
    product_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.CATALOG_VIEW))
):
    service = CatalogService(db)
    try:
        product = service.get_product_or_404(product_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if not product.image_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product has no image")
    path = os.path.join(get_settings().product_image_dir, product.image_path)
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image file is missing")
    ext = os.path.splitext(product.image_path)[1].lower()
    media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext[1:], "application/octet-stream")
    return Response(content=open(path, "rb").read(), media_type=media_type)
