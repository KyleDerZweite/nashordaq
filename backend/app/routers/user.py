from fastapi import APIRouter

from app.auth import CurrentUser
from app.schemas import UserResponse

router = APIRouter(tags=["user"])


@router.get("/user/me", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        balance=user.balance,
        created_at=user.created_at,
    )
