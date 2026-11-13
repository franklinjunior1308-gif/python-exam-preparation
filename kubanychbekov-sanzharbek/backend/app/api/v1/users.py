from fastapi import APIRouter

from app.api.deps import DbDep, OrgDep
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services import users as service

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
def list_users(ctx: OrgDep, db: DbDep) -> list[UserOut]:
    """Members of the organization with their role (administrators only)."""
    return service.list_users(db, ctx)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, ctx: OrgDep, db: DbDep) -> UserOut:
    return service.create_user(db, ctx, data)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, ctx: OrgDep, db: DbDep) -> UserOut:
    return service.update_user(db, ctx, user_id, data)
