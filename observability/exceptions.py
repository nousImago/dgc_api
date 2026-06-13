from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DGCError(Exception):
    """Base class for all domain/business exceptions."""

    status_code: int = 400
    code: str = "error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFoundError(DGCError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(DGCError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(DGCError):
    status_code = 403
    code = "forbidden"


class ConflictError(DGCError):
    status_code = 409
    code = "conflict"


class ValidationError(DGCError):
    status_code = 422
    code = "validation_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DGCError)
    async def dgc_error_handler(request: Request, exc: DGCError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={"code": "not_found", "message": "Resource not found"},
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": "Internal server error"},
        )
