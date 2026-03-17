from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from pulse_api.database import engine
from pulse_api.routers import dev


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()


app = FastAPI(title="Pulse API", lifespan=lifespan)

app.include_router(dev.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
