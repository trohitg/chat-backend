import os
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    API_VERSION: str = "v1"
    PROJECT_NAME: str = "Chat Backend API"
    DEBUG: bool = Field(default=False)
    
    # OpenRouter API - REQUIRED: Set in environment variables
    OPENROUTER_API_KEY: str = Field(description="OpenRouter API key - MUST be set via environment variable")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1")
    
    # Default model (via OpenRouter)
    DEFAULT_MODEL: str = Field(default="gpt-oss-120b")
    AVAILABLE_MODELS: list = Field(default=[
        "gpt-oss-120b",
        "meta-llama/llama-3.3-70b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
        "meta-llama/llama-3.1-70b-instruct",
        "qwen/qwen-2.5-72b-instruct"
    ])
    
    # LM Studio API (Optional)
    LM_STUDIO_ENABLED: bool = Field(default=True)
    LM_STUDIO_URL: str = Field(default="http://10.20.178.142:1234")
    LM_STUDIO_DEFAULT_MODEL: str = Field(default="gemma-3-1b-it")
    LM_STUDIO_AVAILABLE_MODELS: list = Field(default=[
        "gemma-3-1b-it",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant", 
        "mixtral-8x7b-32768",
        "gemma-7b-it"
    ])
    
    # Backend Selection
    DEFAULT_LLM_BACKEND: str = Field(default="openrouter")  # "openrouter" or "lm_studio"
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://chatuser:chatpass123@postgres:5432/chatdb")
    
    # Redis
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    CACHE_TTL: int = Field(default=3600)  # 1 hour
    
    # Security - REQUIRED: Set strong secret key in environment variables
    SECRET_KEY: str = Field(description="Strong secret key - MUST be set via environment variable")
    ALLOWED_HOSTS: list = Field(default=["*"])
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    
    # Razorpay Payment Gateway - REQUIRED: Set in environment variables  
    RAZORPAY_KEY_ID: str = Field(description="Razorpay Key ID - MUST be set via environment variable")
    RAZORPAY_KEY_SECRET: str = Field(description="Razorpay Key Secret - MUST be set via environment variable") 
    RAZORPAY_WEBHOOK_SECRET: str = Field(description="Razorpay Webhook Secret - MUST be set via environment variable")
    
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()