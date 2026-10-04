import logging
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.chat import chat_router
from api.health import health_router
from api.ui import ui_router
from config.logger import setup_logger
from config.settings import settings
from inference.graph import build_graph
from inference.pipeline_definition import pipeline


warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings:",
    category=UserWarning,
    module="pydantic.main",
)
setup_logger()

logger = logging.getLogger(__name__)
logger.info("Starting Sina-infer with settings: %s", settings.as_log_dict())


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline.init()
    app.state.graph = build_graph()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(ui_router)
