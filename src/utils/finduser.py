from typing import Any, Dict, List, Optional
import json

from jose import jwt


def get_token_info(token: str, verify: bool = False, secret: Optional[str] = None,
                   algorithms: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return all information contained in a JWT token.

    - If `verify` is True, the token will be verified using `secret` and
      `algorithms` (mirrors `jose.jwt.decode`).
    - If `verify` is False (default), the header and claims are returned
      without verification using jose's unverified helpers. If those fail,
      a best-effort payload decode is attempted.

    Returns a dict with keys: `header`, `payload`, `raw_token`.
    """
    header: Dict[str, Any] = {}
    payload: Dict[str, Any] = {}

    if not token:
        return {"header": header, "payload": payload, "raw_token": token}

    # Try to get the header unverified (fast and safe for inspection)
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        header = {}

    if verify:
        if not secret or not algorithms:
            raise ValueError("`secret` and `algorithms` are required when verify=True")
        # This will raise if verification fails
        payload = jwt.decode(token, secret, algorithms=algorithms)
    else:
        # Attempt to get claims without verification
        try:
            payload = jwt.get_unverified_claims(token)
        except Exception:
            # Fallback: base64-decode the payload segment
            try:
                from base64 import urlsafe_b64decode

                parts = token.split(".")
                if len(parts) >= 2:
                    b = parts[1]
                    # Add padding if necessary
                    padding = "=" * (-len(b) % 4)
                    decoded = urlsafe_b64decode(b + padding)
                    payload = json.loads(decoded.decode("utf-8"))
            except Exception:
                payload = {}

    return {"header": header, "payload": payload, "raw_token": token}


def extract_user_info(token: str) -> Dict[str, Optional[Any]]:
    """Convenience helper to extract common user fields from a token payload.

    Returns a dict with keys commonly used for identity: `sub`, `user_id`,
    `username`, `email`, `roles`, and the entire `claims`.
    """
    info = get_token_info(token, verify=False)
    claims = info.get("payload") or {}

    return {
        "sub": claims.get("sub"),
        "user_id": claims.get("user_id") or claims.get("id"),
        "username": claims.get("username") or claims.get("preferred_username") or claims.get("name"),
        "email": claims.get("email"),
        "roles": claims.get("roles") or claims.get("role") or claims.get("scope"),
        "claims": claims,
    }


__all__ = ["get_token_info", "extract_user_info"]
