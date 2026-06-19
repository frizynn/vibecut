import logging
from datetime import UTC, datetime
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.schema import SessionUser

# LOCAL_MODE is owned by db.py (the single source of truth). Re-exported here so
# existing imports `from auth.routes import LOCAL_MODE` keep working.
from db import LOCAL_MODE, get_db_pool

logger = logging.getLogger(__name__)

# Local single-user mode: no login, no Google OAuth. The app runs as one
# implicit local user. This is the default for a personal, self-hosted install
# (set LOCAL_MODE=false to require real BetterAuth sessions, e.g. in the cloud).
LOCAL_USER_ID = "local-user"
_LOCAL_USER = SessionUser(
    user_id=LOCAL_USER_ID,
    email="local@vibecut.app",
    name="Local",
    image=None,
)

# HTTPS production uses the __Secure- prefix; dev may use the plain name.
_BETTER_AUTH_COOKIE_NAMES = (
    "__Secure-better-auth.session_token",
    "better-auth.session_token",
)


def _extract_session_token_from_cookies(request: Request) -> str | None:
    """
    Better Auth stores a signed cookie value as "<token>.<signature>".
    Extract the raw token used in the session table.
    """
    raw_cookie_value: str | None = None
    for cookie_name in _BETTER_AUTH_COOKIE_NAMES:
        raw_cookie_value = request.cookies.get(cookie_name)
        if raw_cookie_value:
            break
    if not raw_cookie_value:
        return None

    decoded_cookie = unquote(raw_cookie_value)
    token = decoded_cookie.split(".", 1)[0]
    return token or None


async def ensure_local_user() -> None:
    """Seed the implicit local user so project/asset foreign keys resolve."""
    if not LOCAL_MODE:
        return
    now = datetime.now(UTC).isoformat()
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # SQLite has no triggers/defaults here, so supply id + timestamps and use
        # INSERT OR IGNORE (this path only runs in LOCAL_MODE / SQLite).
        await conn.execute(
            """
            INSERT OR IGNORE INTO "user"
                (id, name, email, "emailVerified", "createdAt", "updatedAt")
            VALUES ($1, $2, $3, 1, $4, $4)
            """,
            LOCAL_USER_ID,
            _LOCAL_USER.name,
            _LOCAL_USER.email,
            now,
        )
    logger.info("LOCAL_MODE on — running as implicit local user (no login).")


router = APIRouter(prefix="/auth", tags=["auth"])


async def get_current_user(
    request: Request,
) -> SessionUser:
    """
    FastAPI dependency. In LOCAL_MODE returns the implicit local user without
    any session. Otherwise reads the BetterAuth session token from the HttpOnly
    cookie and validates it against the session/user tables in Postgres.
    """
    if LOCAL_MODE:
        return _LOCAL_USER

    session_token = _extract_session_token_from_cookies(request)
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.name, u.email, u.image
            FROM session s
            JOIN "user" u ON u.id = s."userId"
            WHERE s.token = $1 AND s."expiresAt" > now()
            """,
            session_token,
        )

    if row is None:
        logger.warning("Invalid or expired session token attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return SessionUser(
        user_id=str(row["id"]),
        email=str(row["email"]),
        name=str(row["name"]),
        image=str(row["image"]) if row["image"] else None,
    )


@router.get("/me", response_model=SessionUser)
async def get_me(user: SessionUser = Depends(get_current_user)) -> SessionUser:
    return user
