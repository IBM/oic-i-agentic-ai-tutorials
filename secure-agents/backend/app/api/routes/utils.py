from fastapi import APIRouter

router = APIRouter()


@router.get("/health-check/", include_in_schema=False)
async def health_check() -> bool:
    return True
