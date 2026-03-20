from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from pulse_api.database import engine
from pulse_api.routers import anomalies, dev, nodes, pipelines, ws
from pulse_api.services.live_simulator import run_live_simulation


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_live_simulation, "interval", seconds=30)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title="Pulse API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dev.router)
app.include_router(pipelines.router)
app.include_router(nodes.router)
app.include_router(anomalies.router)
app.include_router(ws.router)


@app.middleware("http")
async def add_cors_fallback(request: Request, call_next: object) -> Response:
    response: Response = await call_next(request)  # type: ignore[operator]
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
