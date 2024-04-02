import os
import hashlib
from uuid import uuid4
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from passlib.context import CryptContext
from jose import jwt, JWTError
from database import SessionLocal
from models import User, RevokedToken

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/login")


class RegisterUserRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginUserRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(register_user_request: RegisterUserRequest, db: db_dependency):
    user = User(
        username=register_user_request.username,
        email=register_user_request.email,
        hashed_password=bcrypt_context.hash(register_user_request.password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"username": user.username, "email": user.email}


@router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(login_user_request: LoginUserRequest, db: db_dependency):
    email = login_user_request.email
    password = login_user_request.password

    if not email or not password:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    user = authenticate_user(email, password, db)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate credentials")

    token = create_access_token(user.email, user.id, timedelta(minutes=30))

    return {"user": {"username": user.username, "email": user.email},
            "access_token": token, "token_type": "bearer"}


@router.get("/logout", status_code=status.HTTP_200_OK)
async def logout_user(db: db_dependency, token: str = Depends(oauth2_bearer)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        token_id = payload.get("jti")

        if token_id is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")

        if db.query(RevokedToken).filter(RevokedToken.token_id == token_id).first():
            raise HTTPException(status_code=401, detail="Unauthorized access")

        revoked_token = RevokedToken(token_id=token_id)
        db.add(revoked_token)
        db.commit()

        return {"message": "Logout successful"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


def authenticate_user(email: str, password: str, db):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return False

    if not bcrypt_context.verify(password, user.hashed_password):
        return False

    return user


def create_access_token(email: str, user_id: int, expires_delta: timedelta = None):
    uuid_str = str(uuid4())
    unique_string = f"{user_id}-{email}-{uuid_str}"
    token_id = hashlib.md5(unique_string.encode()).hexdigest()

    encode = {'sub': email, 'id': user_id, 'jti': token_id}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})

    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)], db: db_dependency):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_id = payload.get('jti')

        if email is None or token_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Could not validate credentials")

        user = db.query(User).filter(User.email == email).first()

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Unauthorized access")

        token_revoked = db.query(RevokedToken).filter(RevokedToken.token_id == token_id).first()

        if token_revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Unauthorized access")

        return {"user": {"id": user.id, "username": user.username, "email": user.email},
                "access_token": token, "token_type": "bearer"}

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Could not validate credentials")
