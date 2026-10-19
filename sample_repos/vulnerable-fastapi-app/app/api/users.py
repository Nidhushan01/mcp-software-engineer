from fastapi import APIRouter


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{username}")
def get_user(username: str) -> dict[str, str]:
    return {"username": username}
