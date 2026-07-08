import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import SessionDep
from app.models import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message
from app.tables import Item

router = APIRouter()


@router.get("/", response_model=ItemsPublic)
def read_items(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve all feedback items (admin only).
    """
    count_statement = select(func.count()).select_from(Item)
    count = session.exec(count_statement).one()
    statement = select(Item).offset(skip).limit(limit)
    items = session.exec(statement).all()
    return ItemsPublic(
        data=[ItemPublic.model_validate(item) for item in items], count=count
    )


@router.get("/{id}", response_model=ItemPublic)
def read_item(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """
    Get feedback item by ID (admin only).
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# TODO: The create and update item should only be available to superusers/admins!
@router.post("/", response_model=ItemPublic)
def create_item(*, session: SessionDep, item_in: ItemCreate) -> Any:
    """
    Create new feedback item (no authentication required - anonymous feedback).
    """
    item = Item.model_validate(item_in)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update a feedback item (admin only).
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(
    session: SessionDep,
    id: uuid.UUID,
) -> Message:
    """
    Delete a feedback item (admin only).
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")
