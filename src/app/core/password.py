from fastapi import HTTPException
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

pwd_context = PasswordHasher()


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except InvalidHash:
        raise HTTPException(status_code=400, detail="Invalid hash format.")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
