from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .services.chat_service import ChatService
from .core.database import get_db
from .core.cache import cache
from .services.openrouter_service import openrouter_service
from .services.lm_studio import lm_studio_service
from .core.config import settings

def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    """Create chat service with dependencies"""
    # Include LM Studio service only if enabled
    lm_studio = lm_studio_service if settings.LM_STUDIO_ENABLED else None
    return ChatService(db, cache, openrouter_service, lm_studio)

# Type aliases for cleaner code
ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]
AsyncDatabaseDependency = Annotated[AsyncSession, Depends(get_db)]