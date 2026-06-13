from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, has_permission
from domain.product.model import Product, ProductRatingDimension
from domain.product.schema import ProductCreate, ProductOut
from integrations.db.repositories import product_repo
from observability.exceptions import ConflictError

router = APIRouter()


@router.get("", response_model=list[ProductOut])
async def list_products(db: AsyncSession = Depends(get_db)) -> list[Product]:
    return await product_repo.list_all(db)


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_permission("product.manage"))],
)
async def create_product(
    payload: ProductCreate, db: AsyncSession = Depends(get_db)
) -> Product:
    if await product_repo.get_by_code(db, payload.code) is not None:
        raise ConflictError(f"Product already exists: {payload.code}")
    product = Product(
        code=payload.code,
        name=payload.name,
        kind=payload.kind,
        active=True,
    )
    product.dimensions = [
        ProductRatingDimension(
            name=d.name, data_type=d.data_type, position=d.position
        )
        for d in payload.dimensions
    ]
    return await product_repo.save(db, product)
