import time
import uuid
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.chat import ChatSession, ChatMessage as ChatMessageModel
from ..services.openrouter_service import OpenRouterService
from ..services.lm_studio import LMStudioService
from ..core.config import settings
from ..core.cache import CacheService
import structlog

logger = structlog.get_logger()

class ChatService:
    def __init__(self, db: AsyncSession, cache: CacheService, openrouter: OpenRouterService, lm_studio: Optional[LMStudioService] = None):
        self.db = db
        self.cache = cache
        self.openrouter = openrouter
        self.lm_studio = lm_studio
        
    def _get_llm_service(self, backend: Optional[str] = None):
        """Get the appropriate LLM service based on backend selection"""
        selected_backend = backend or settings.DEFAULT_LLM_BACKEND
        
        if selected_backend == "lm_studio" and self.lm_studio and settings.LM_STUDIO_ENABLED:
            return self.lm_studio
        else:
            # Default to OpenRouter
            return self.openrouter
    
    async def create_session(self) -> ChatSession:
        """Create a new chat session"""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session = ChatSession(session_id=session_id)
        self.db.add(session)
        await self.db.commit()
        
        logger.info("Session created", session_id=session_id)
        return session
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID"""
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def send_message(
        self, 
        session_id: str, 
        message: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7,
        use_cache: bool = True,
        model: Optional[str] = None,
        backend: Optional[str] = None
    ) -> Dict:
        """Send message and get response"""
        # Validate session exists
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Get conversation history
        message_history = await self._get_message_history(session_id)
        message_history.append({"role": "user", "content": message})
        
        # Call selected LLM service
        llm_service = self._get_llm_service(backend)
        result = await llm_service.chat_completion(
            messages=message_history,
            session_id=session_id,
            db=self.db,
            max_tokens=max_tokens,
            temperature=temperature,
            use_cache=use_cache,
            model=model
        )
        
        return {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "content": result["response"],
            "role": "assistant",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    async def send_text_message(
        self,
        session_id: str,
        message: str,
        image_filename: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        use_cache: bool = True,
        model: Optional[str] = None,
        backend: Optional[str] = None
    ) -> Dict:
        """Send text message with optional image filename reference"""
        # Validate session exists
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        try:
            # Store user message with image filename reference if provided
            user_msg = ChatMessageModel(
                session_id=session_id,
                role="user",
                content=message,
                image_url=image_filename  # Store filename reference in existing field
            )
            self.db.add(user_msg)
            
            await self.db.commit()
            
            # Send only the text message to AI (no conversation history)
            text_only_messages = [{"role": "user", "content": message}]
            
            # Get AI response to only the current text message
            llm_service = self._get_llm_service(backend)
            result = await llm_service.chat_completion(
                messages=text_only_messages,
                session_id=session_id,
                db=self.db,
                max_tokens=max_tokens,
                temperature=temperature,
                use_cache=use_cache,
                model=model
            )
            
            logger.info(
                "Text message processed successfully",
                session_id=session_id,
                image_filename=image_filename,
                message_length=len(message)
            )
            
            return {
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "content": result["response"],
                "role": "assistant",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "image_filename": image_filename
            }
            
        except Exception as e:
            logger.error("Failed to save text message", error=str(e), session_id=session_id)
            await self.db.rollback()
            raise
    
    async def get_message_history(self, session_id: str) -> List[Dict]:
        """Get all messages for a session"""
        # Validate session exists
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        result = await self.db.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at)
        )
        messages = result.scalars().all()
        
        return [
            {
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(msg.created_at, 'strftime') else str(msg.created_at),
                "image_filename": msg.image_url  # Reusing image_url field for filename
            }
            for msg in messages
        ]
    
    async def delete_session(self, session_id: str) -> None:
        """Delete session and all messages"""
        # Delete messages
        await self.db.execute(
            ChatMessageModel.__table__.delete().where(ChatMessageModel.session_id == session_id)
        )
        
        # Delete session
        await self.db.execute(
            ChatSession.__table__.delete().where(ChatSession.session_id == session_id)
        )
        
        await self.db.commit()
        logger.info("Session deleted", session_id=session_id)
    
    async def _get_message_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for API call"""
        result = await self.db.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at)
        )
        messages = result.scalars().all()
        return [{"role": msg.role, "content": msg.content} for msg in messages]