from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.product.model import Product


async def get_by_code(session: AsyncSession, code: str) -> Product | None:
    """Load a product with its declared rating dimensions (selectin)."""
    result = await session.execute(select(Product).where(Product.code == code))
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[Product]:
    result = await session.execute(select(Product).order_by(Product.code))
    return list(result.scalars().all())


async def save(session: AsyncSession, product: Product) -> Product:
    session.add(product)
    await session.flush()
    await session.refresh(product)
    return product
