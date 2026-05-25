from fastapi import APIRouter

from .analytics import router as analytics_router
from .auth import router as auth_router
from .flights import router as flights_router
from .predictions import router as predictions_router
from .tickets import router as tickets_router
from .user_data import router as user_data_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(user_data_router)
router.include_router(flights_router)
router.include_router(tickets_router)
router.include_router(predictions_router)
router.include_router(analytics_router)
