import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.catalog import Product
from app.models.rbac import User
from app.modules.catalog.labels import (
    InvalidLabelDataError,
    generate_barcode_png,
    generate_label_sheet_png,
    generate_qr_png,
)
from app.modules.catalog.schemas import (
    CategoryCreateRequest,
    CategoryResponse,
    HSNCreateRequest,
    HSNResponse,
    ProductCreateRequest,
    ProductResponse,
    UOMCreateRequest,
    UOMResponse,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


def _to_product_response(service: CatalogService, product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        sku=product.sku,
        barcode=product.barcode,
        name=product.name,
        mrp=product.mrp,
        sale_price=product.sale_price,
        purchase_price=product.purchase_price,
        tax_rate_percent=service.hsn_current_rate(product.hsn_code_id) if product.hsn_code_id else None,
        tracks_batches=product.tracks_batches,
        tracks_serials=product.tracks_serials,
        tracks_expiry=product.tracks_expiry,
        is_active=product.is_active,
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
    return _to_product_response(service, product)


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
