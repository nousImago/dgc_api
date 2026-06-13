from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, has_permission
from domain.customer.model import Customer
from domain.customer.schema import CustomerCreate, CustomerOut
from integrations.db.repositories import customer_repo
from observability.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=list[CustomerOut])
async def list_customers(db: AsyncSession = Depends(get_db)) -> list[Customer]:
    return await customer_repo.list_all(db)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: int, db: AsyncSession = Depends(get_db)
) -> Customer:
    customer = await customer_repo.get_by_id(db, customer_id)
    if customer is None:
        raise NotFoundError(f"Unknown customer: {customer_id}")
    return customer


@router.post(
    "",
    response_model=CustomerOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_permission("customer.manage"))],
)
async def create_customer(
    payload: CustomerCreate, db: AsyncSession = Depends(get_db)
) -> Customer:
    customer = Customer(
        external_ref=payload.external_ref,
        full_name=payload.full_name,
        sex=payload.sex,
        date_of_birth=payload.date_of_birth,
    )
    return await customer_repo.save(db, customer)
