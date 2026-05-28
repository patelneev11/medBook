import logging
import time
import uuid

from fastapi import FastAPI, Request

logger = logging.getLogger("mednotebook.requests")


def add_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        status = response.status_code
        msg = (
            f"request_id={request_id} "
            f"{request.method} {request.url.path} "
            f"- {status} - {duration_ms:.1f}ms"
        )

        if status >= 500:
            logger.error(msg)
        elif status >= 400:
            logger.warning(msg)
        else:
            logger.info(msg)

        response.headers["X-Request-ID"] = request_id
        return response
