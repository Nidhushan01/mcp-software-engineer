from fastapi import APIRouter, HTTPException

from app.services.auth_service import create_access_token


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token")
def login(username: str, password: str) -> dict[str, str]:
    # Deliberately simplified for this vulnerable training repository.
    if username != "admin" or password != "admin":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(username), "token_type": "bearer"}
