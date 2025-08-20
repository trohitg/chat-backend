from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time
from functools import wraps

# Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Active connections')
CHAT_REQUESTS = Counter('chat_requests_total', 'Total chat requests', ['status'])
CACHE_HITS = Counter('cache_hits_total', 'Cache hits', ['type'])
CACHE_MISSES = Counter('cache_misses_total', 'Cache misses', ['type']) 
CACHE_ERRORS = Counter('cache_errors_total', 'Cache errors', ['type'])
TOKENS_USED = Counter('tokens_used_total', 'Total tokens used')

def track_request_metrics(func):
    """Decorator to track request metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            REQUEST_COUNT.labels(method="POST", endpoint="/chat", status="success").inc()
            return result
        except Exception as e:
            REQUEST_COUNT.labels(method="POST", endpoint="/chat", status="error").inc()
            raise
        finally:
            REQUEST_DURATION.labels(method="POST", endpoint="/chat").observe(time.time() - start_time)
    return wrapper

def get_metrics():
    """Get Prometheus metrics"""
    return generate_latest()