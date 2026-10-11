import logging
import os
from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token
from key_value.aio.stores.filetree import FileTreeStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

import db

logger = logging.getLogger("calculator-mcp")

GOOGLE_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]


@dataclass(frozen=True)
class User:
    sub: str  # stable Google user id
    email: str | None


def build_auth() -> GoogleProvider | None:
    """Google sign-in for the whole server, or None when not configured.

    FastMCP has no anonymous mode: once a provider is set, every request to
    /mcp needs a valid token, so leaving GOOGLE_CLIENT_ID unset keeps the
    server open (local development).
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        logger.warning("GOOGLE_CLIENT_ID not set: server is running WITHOUT auth")
        return None

    signing_key = os.environ["JWT_SIGNING_KEY"]

    # OAuth state (client registrations, refresh tokens) lives on the volume so
    # users stay signed in across redeploys; it is encrypted at rest.
    storage = FernetEncryptionWrapper(
        FileTreeStore(
            data_directory=os.path.join(os.path.dirname(db.DB_PATH), "oauth")
        ),
        source_material=signing_key,
        salt="mcp-toy-oauth-storage",
    )

    return GoogleProvider(
        client_id=client_id,
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        base_url=os.environ["PUBLIC_BASE_URL"],
        required_scopes=GOOGLE_SCOPES,
        jwt_signing_key=signing_key,
        client_storage=storage,
    )


def current_user() -> User:
    """The signed-in user for this request; raises if there isn't one."""
    token = get_access_token()
    if token is None:
        raise ToolError("You must be signed in to use this tool.")
    sub = token.claims.get("sub")
    if not sub:
        raise ToolError("Could not identify your account.")
    return User(sub=sub, email=token.claims.get("email"))
