from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

# from passlib.context import CryptContext
from src.app.core.database import get_db
from sqlalchemy.orm import Session


from src.app.domain.auth.crud import auth_crud as crud


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
ALGORITHM = "HS256"


from src.app.core.token import decode_token


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        email = decode_token(token)
        user = crud.get_user_by_email(db, email=email)
        if user is None:
            raise HTTPException(status_code=401, detail="User is None")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
