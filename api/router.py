from fastapi import APIRouter

from api.v1 import auth

api_router = APIRouter()

api_router.include_router(
    auth.router,
    prefix="/v1/auth",
    tags=["Auth"],
)

# Register additional v1 routers here as features are added, e.g.:
#   from api.v1 import users
#   api_router.include_router(users.router, prefix="/v1/users", tags=["Users"])
