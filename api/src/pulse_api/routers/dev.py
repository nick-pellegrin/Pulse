from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from pulse_api.config import settings
from pulse_api.database import get_session
from pulse_api.services.synthetic.generator import SeedResult, seed_database

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/seed", response_model=SeedResult)
async def seed(session: AsyncSession = Depends(get_session)) -> SeedResult:
    """Seed the database with 90 days of synthetic pipeline data.

    Clears all existing synthetic pipelines and generates fresh data for:
      - jaffle-shop-analytics (12 nodes, 1 run/day)
      - payments-pipeline (28 nodes, 4 runs/day)
      - ml-feature-store (45 nodes, 2 runs/day)

    Development only — returns 404 in production.
    """
    if settings.env == "production":
        raise HTTPException(status_code=404, detail="Not found")
    return await seed_database(session)
