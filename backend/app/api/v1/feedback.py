from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from pymongo.asynchronous.database import AsyncDatabase

from app.database.documents import FeedbackDocument
from app.database.repositories.documents import FeedbackRepository
from app.database.repositories.users import UserRecord
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_database
from app.isl.schemas import FeedbackCreateRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["translation feedback"])


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    payload: FeedbackCreateRequest,
    database: AsyncDatabase = Depends(get_database),
    user: UserRecord = Depends(get_current_user),
) -> FeedbackResponse:
    created_at = datetime.now(timezone.utc)
    record = await FeedbackRepository(database).create(
        FeedbackDocument(
            user_id=user.id,
            translation_id=str(payload.translation_id),
            session_id=str(payload.session_id),
            sign_id=payload.sign_id,
            rating=payload.rating,
            correction=payload.correction,
            feedback_type=payload.feedback_type,
            verification_status="pending_review",
            created_at=created_at,
        )
    )
    return FeedbackResponse(
        id=str(record.id),
        verification_status="pending_review",
        created_at=record.created_at,
    )
