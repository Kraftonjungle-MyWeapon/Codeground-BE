from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from src.app.core.database import get_db
from src.app.domain.auth.crud import auth_crud as crud
from src.app.core.token import decode_token
from jose import JWTError

def get_current_user(
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    print("====[get_current_user]====")
    print(f"access_token (쿠키에서): {access_token}")
    # (추가: 토큰이 아예 없는 경우)
    if not access_token:
        print("[ERROR] access_token 쿠키 없음")
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        email = decode_token(access_token)
        print(f"디코딩된 email: {email}")
        user = crud.get_user_by_email(db, email=email)
        print(f"조회된 user: {user}")
        if user is None:
            print("[ERROR] 해당 이메일의 유저 없음")
            raise HTTPException(status_code=401, detail="User is None")
        print("[SUCCESS] 인증된 user 반환")
        print("=======================")
        return user
    except JWTError as e:
        print(f"[ERROR] JWT 디코딩 에러: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")