from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.history import router as history_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.isl import router as isl_router
from app.api.v1.realtime import router as realtime_router
from app.api.v1.speech import router as speech_router
from app.api.v1.users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(history_router)
router.include_router(realtime_router)
router.include_router(isl_router)
router.include_router(feedback_router)
router.include_router(speech_router)
