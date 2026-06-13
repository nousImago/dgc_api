from fastapi import APIRouter

from api.v1 import auth, customers, policies, premium_due, products, quotes

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])
api_router.include_router(customers.router, prefix="/v1/customers", tags=["Customers"])
api_router.include_router(
    premium_due.router, prefix="/v1/customers", tags=["Premium Due"]
)
api_router.include_router(products.router, prefix="/v1/products", tags=["Products"])
api_router.include_router(policies.router, prefix="/v1/policies", tags=["Policies"])
api_router.include_router(quotes.router, prefix="/v1/quotes", tags=["Quotes"])
