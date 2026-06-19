import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# because env should be loaded before importing the routes. is it a hack? idts.
from ai.routes import router as ai_router  # noqa: E402
from api.routes import router as api_router  # noqa: E402
from auth.routes import ensure_local_user  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from db import close_db_pool, init_local_schema  # noqa: E402
from media.routes import router as media_router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up")
    await init_local_schema()
    await ensure_local_user()
    yield
    logger.info("Shutting down — closing DB pool")
    await close_db_pool()


app = FastAPI(lifespan=lifespan, redirect_slashes=False)

# localhost for dev; in production set BETTER_AUTH_URL to your public origin.
_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
]
_prod_origin = os.getenv("BETTER_AUTH_URL")
if _prod_origin and _prod_origin.startswith("https://"):
    _ALLOWED_ORIGINS.append(_prod_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/beep")
async def beep() -> dict:
    return {"message": "boop"}


app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(api_router)
app.include_router(media_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "3000")),
        reload=os.getenv("NODE_ENV") != "production",
    )
