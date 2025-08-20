from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON
from sqlalchemy.sql import func
from ..core.database import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True)
    user_id = Column(String(255), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True)
    role = Column(String(50))  # user, assistant
    content = Column(Text)
    image_url = Column(String(500), nullable=True)  # Filename reference for uploaded image
    tokens_used = Column(Integer, nullable=True)
    response_time = Column(Float, nullable=True)  # in seconds
    model_used = Column(String(100), nullable=True)
    message_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ApiUsage(Base):
    __tablename__ = "api_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=True)
    user_id = Column(String(255), index=True, nullable=True)
    endpoint = Column(String(255))
    tokens_used = Column(Integer, default=0)
    response_time = Column(Float)
    success = Column(String(10))  # success, error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())