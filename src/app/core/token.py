from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Optional

from fastapi import HTTPException
from jose import ExpiredSignatureError, jwt, JWTError

from src.app.config.config import settings

ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    expires_delta: Optional[int] = None,
    key: str = settings.SECRET_KEY,
    issuer: str = "codeground",
    audience: Optional[str] = "codeground",
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_delta or settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": subject,  # subject (ex: user email or id)
        "iat": int(now.timestamp()),  # issued at (timestamp)
        "exp": int(expire.timestamp()),  # expiration (timestamp)
        "iss": issuer,  # issuer
        "aud": audience,
        "jti": str(uuid4()),
    }
    encoded_jwt = jwt.encode(payload, key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str, key: str = settings.SECRET_KEY, issuer: str = "codeground", audience: str = "codeground"):
    try:
        payload = jwt.decode(token, key, algorithms=[ALGORITHM], audience=audience, issuer=issuer)
        return payload.get("sub")
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token is expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
