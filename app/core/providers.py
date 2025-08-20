"""
Simplified LLM Provider Management
Unified provider/model selection system
"""
from typing import Optional, Tuple, Dict, List
from pydantic import BaseModel
from .config import settings

# Available provider/model combinations
AVAILABLE_PROVIDERS = [
    # OpenRouter providers
    "openrouter/gpt-oss-120b",
    "openrouter/meta-llama/llama-3.3-70b-instruct", 
    "openrouter/meta-llama/llama-3.1-8b-instruct",
    "openrouter/meta-llama/llama-3.1-70b-instruct",
    "openrouter/qwen/qwen-2.5-72b-instruct",
    
    # LM Studio providers (only if enabled)
    *([
        "lm_studio/gemma-3-1b-it",
        "lm_studio/llama-3.3-70b-versatile", 
        "lm_studio/llama-3.1-8b-instant",
        "lm_studio/mixtral-8x7b-32768",
        "lm_studio/gemma-7b-it"
    ] if settings.LM_STUDIO_ENABLED else [])
]

def parse_provider(provider: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Parse provider string into (backend, model)
    
    Args:
        provider: Format "backend/model" (e.g., "lm_studio/gemma-3-1b-it")
                 If None, uses default backend
    
    Returns:
        Tuple of (backend, model)
    """
    if not provider:
        # Use default backend with its default model
        backend = settings.DEFAULT_LLM_BACKEND
        if backend == "lm_studio":
            model = settings.LM_STUDIO_DEFAULT_MODEL
        else:
            backend = "openrouter"
            model = settings.DEFAULT_MODEL
        return backend, model
    
    if "/" not in provider:
        # Just backend specified, use default model
        backend = provider
        if backend == "lm_studio":
            model = settings.LM_STUDIO_DEFAULT_MODEL
        elif backend == "openrouter":
            model = settings.DEFAULT_MODEL
        else:
            backend = "openrouter"
            model = settings.DEFAULT_MODEL
        return backend, model
    
    # Full provider/model specified
    backend, model = provider.split("/", 1)
    return backend, model

def get_available_providers() -> Dict:
    """Get all available providers in a simple format"""
    providers_by_backend = {}
    
    for provider in AVAILABLE_PROVIDERS:
        backend, model = provider.split("/", 1)
        if backend not in providers_by_backend:
            providers_by_backend[backend] = []
        providers_by_backend[backend].append(model)
    
    return {
        "available_providers": AVAILABLE_PROVIDERS,
        "providers_by_backend": providers_by_backend,
        "default_provider": f"{settings.DEFAULT_LLM_BACKEND}/{settings.LM_STUDIO_DEFAULT_MODEL if settings.DEFAULT_LLM_BACKEND == 'lm_studio' else settings.DEFAULT_MODEL}"
    }

def validate_provider(provider: str) -> bool:
    """Check if a provider is available"""
    return provider in AVAILABLE_PROVIDERS