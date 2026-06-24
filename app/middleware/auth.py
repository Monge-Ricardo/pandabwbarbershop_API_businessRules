import jwt
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Header, HTTPException, status, Depends
from passlib.context import CryptContext
from app.config import settings
from app.clients.crud_client import crud_client

import bcrypt

def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt."""
    pw_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a hash."""
    pw_bytes = plain_password.encode('utf-8')
    hash_bytes = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a secure HS256 JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt

async def resolve_user_role(user_id: str) -> str:
    """
    Resolves the system role of a user.
    If the user has a barbershop membership with role 'owner' or 'barber', returns that.
    Otherwise, defaults to 'customer'.
    """
    memberships = await crud_client.list_members(user_id=user_id)
    if memberships:
        # Check if there is an owner membership
        for m in memberships:
            if m["role"].upper() == "OWNER":
                return "owner"
        # Check if there is a barber membership
        for m in memberships:
            if m["role"].upper() == "BARBER":
                return "barber"
    return "customer"

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency to extract and validate the JWT token.
    Supports both secure JWT tokens and legacy development mock tokens.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autorización faltante o malformado."
        )
    token = authorization.split(" ")[1]
    
    # Check for legacy mock token (compatibility mode)
    if "mock_token_for_user_" in token:
        user_id = token.split("mock_token_for_user_")[1]
        user = await crud_client.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario de token de prueba no encontrado."
            )
        user["role"] = await resolve_user_role(user_id)
        return user

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token no válido (falta ID de usuario)."
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado."
        )
        
    user = await crud_client.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario de perfil no encontrado en base de datos."
        )
    
    user["role"] = await resolve_user_role(user_id)
    return user

def require_role(allowed_roles: List[str]):
    """
    FastAPI dependency to restrict endpoints to specific roles.
    """
    async def dependency(current_user: dict = Depends(get_current_user)):
        role = current_user.get("role", "customer").lower()
        if role not in [r.lower() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado. Requiere uno de los siguientes roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return dependency
