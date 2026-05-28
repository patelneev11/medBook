import logging
import traceback

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .exceptions import AppException
from .middleware.cors import add_cors
from .middleware.logging import add_logging
from .routers import documents, health, projects, queries
from .routers.users import auth_router, users_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("mednotebook")

app = FastAPI(
    title="MedNotebook API",
    description="Secure AI-powered document workspace for medical researchers",
    version="0.1.0",
)

add_cors(app)
add_logging(app)


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "code": exc.code},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        content = {
            "error": "Not found",
            "detail": "The requested resource does not exist",
            "code": "NOT_FOUND",
        }
    else:
        content = {
            "error": exc.detail if isinstance(exc.detail, str) else "HTTP error",
            "code": f"HTTP_{exc.status_code}",
        }
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = err.get("loc", ())
        # loc is ("body", "field_name") or ("query", "param") — drop the first segment
        field = ".".join(str(p) for p in loc[1:]) if len(loc) > 1 else ".".join(str(p) for p in loc)
        errors.append({"field": field, "message": err.get("msg", "Invalid value")})
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "code": "VALIDATION_ERROR",
            "detail": errors,
        },
    )


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "code": "SERVER_ERROR"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(queries.router)

app.include_router(api_router)
