from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db import SessionLocal
from security import decode_token
import crud

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if not sub:
            raise ValueError("missing sub")
        user_id = int(sub)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user = crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")

    roles, perms = crud.get_roles_and_permissions(db, user_id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "roles": roles,
        "permissions": perms,
    }

def require_permission(code: str):
    def _guard(ctx = Depends(get_current_user)):
        if code not in ctx["permissions"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso")
        return ctx
    return _guard

def require_role(role: str):
    def _guard(ctx = Depends(get_current_user)):
        if role not in ctx["roles"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        return ctx
    return _guard
