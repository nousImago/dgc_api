from fastapi import APIRouter

from api.v1 import (
    auth,
    parties,
    policies,
    premium_due,
    premium_register,
    products,
    quotes,
    search,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])
api_router.include_router(parties.router, prefix="/v1/parties", tags=["Parties"])
api_router.include_router(
    premium_due.router, prefix="/v1/parties", tags=["Premium Due"]
)
api_router.include_router(products.router, prefix="/v1/products", tags=["Products"])
api_router.include_router(policies.router, prefix="/v1/policies", tags=["Policies"])
api_router.include_router(
    premium_register.router, prefix="/v1/premium-register", tags=["Premium Register"]
)
api_router.include_router(quotes.router, prefix="/v1/quotes", tags=["Quotes"])
api_router.include_router(search.router, prefix="/v1/search", tags=["Search"])
