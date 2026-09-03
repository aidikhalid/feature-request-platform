from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, requests
from app.config import settings
from app.errors import register_exception_handlers

app = FastAPI(
    title="Feature Request & Voting Platform API",
    version="1.0.0",
    description=(
        "Interactive docs are served here because FastAPI derives OpenAPI from the same "
        "Pydantic schemas that validate incoming requests — the docs cannot drift from the code."
    ),
)

# Credentials must be allowed for the session cookie to travel, which in turn means the
# origin list has to be explicit — "*" and credentials are incompatible, by design.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(admin.router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness probe for Compose and any future orchestrator."""
    return {"status": "ok"}
