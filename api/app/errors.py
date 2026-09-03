from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Domain-level failure with an HTTP shape.

    Services raise these instead of returning error tuples, so business rules read as
    plain statements and every route gets the same error envelope for free.
    """

    def __init__(self, status_code: int, code: str, message: str, details: list | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)


class NotFound(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, "not_found", message)


class Forbidden(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(status.HTTP_403_FORBIDDEN, "forbidden", message)


class Unauthorized(AppError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


class Conflict(AppError):
    def __init__(self, message: str, code: str = "conflict"):
        super().__init__(status.HTTP_409_CONFLICT, code, message)


class BadRequest(AppError):
    def __init__(self, message: str, code: str = "bad_request"):
        super().__init__(status.HTTP_400_BAD_REQUEST, code, message)


def _envelope(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def register_exception_handlers(app: FastAPI) -> None:
    """One error shape for the whole API, so the frontend has exactly one thing to parse."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_envelope(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("validation_error", "The submitted data is invalid", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_envelope("http_error", str(exc.detail))
        )
