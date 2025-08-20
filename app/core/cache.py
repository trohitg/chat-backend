import json
import hashlib
import zlib
from typing import Optional, Any, Dict, List
import redis
from .config import settings
import structlog

logger = structlog.get_logger()

# Redis connection with connection pooling
redis_client = redis.ConnectionPool.from_url(
    settings.REDIS_URL, 
    decode_responses=True,
    max_connections=20,
    retry_on_timeout=True
)
redis_conn = redis.Redis(connection_pool=redis_client)

class CacheService:
    def __init__(self):
        self.client = redis_conn
        self.default_ttl = settings.CACHE_TTL
        self.compression_threshold = 1024  # Compress responses > 1KB
    
    def _generate_key(self, prefix: str, data: dict) -> str:
        """Generate a consistent cache key using SHA-256"""
        data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        hash_obj = hashlib.sha256(data_str.encode('utf-8'))
        return f"chat_cache:{prefix}:{hash_obj.hexdigest()[:16]}"
    
    def _get_conversation_key(self, messages: List[Dict[str, str]]) -> str:
        """Generate cache key from user's current question only"""
        if not messages:
            return self._generate_key("simple", {"question": ""})
            
        # Get the last user message (current question)
        current_user_msg = messages[-1] if messages else {}
        
        # Cache based ONLY on the user's current message content
        # This ensures identical questions always hit cache regardless of conversation history
        if current_user_msg.get("role") == "user":
            user_question = current_user_msg.get("content", "").strip().lower()
            cache_data = {"question": user_question}
        else:
            # Fallback for unexpected message structure
            cache_data = {"question": str(current_user_msg)}
            
        return self._generate_key("simple", cache_data)
    
    def _compress_data(self, data: str) -> bytes:
        """Compress data if it's large enough"""
        if len(data) > self.compression_threshold:
            return zlib.compress(data.encode('utf-8'))
        return data.encode('utf-8')
    
    def _decompress_data(self, data: bytes) -> str:
        """Decompress data if needed"""
        try:
            # Try to decompress first
            return zlib.decompress(data).decode('utf-8')
        except (zlib.error, UnicodeDecodeError):
            # If decompression fails, assume it's uncompressed
            return data.decode('utf-8')
    
    def get_chat_response(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Get cached chat response"""
        try:
            key = self._get_conversation_key(messages)
            cached_data = self.client.get(key)
            
            if cached_data:
                logger.info("Cache hit", question=messages[-1].get("content", "")[:50] if messages else "")
                
                # Handle both compressed and uncompressed data
                if isinstance(cached_data, bytes):
                    return self._decompress_data(cached_data)
                return cached_data
            else:
                logger.info("Cache miss", question=messages[-1].get("content", "")[:50] if messages else "")
                return None
                
        except Exception as e:
            logger.error("Cache get error", error=str(e))
            return None
    
    def set_chat_response(self, messages: List[Dict[str, str]], response: str, ttl: Optional[int] = None) -> bool:
        """Cache chat response with compression"""
        try:
            key = self._get_conversation_key(messages)
            ttl = ttl or self.default_ttl
            
            # Compress large responses
            compressed_response = self._compress_data(response)
            success = self.client.setex(key, ttl, compressed_response)
            
            logger.debug("Response cached", question=messages[-1].get("content", "")[:50] if messages else "")
            return success
            
        except Exception as e:
            logger.error("Cache set error", error=str(e))
            return False
    
    
    def health_check(self) -> Dict[str, Any]:
        """Simple health check"""
        try:
            ping_result = self.client.ping()
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "connection": ping_result
            }
        except Exception as e:
            logger.error("Cache health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "connection": False,
                "error": str(e)
            }

cache = CacheService()