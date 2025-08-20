from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from .config import settings
import structlog

logger = structlog.get_logger()

# Convert PostgreSQL URL to async version
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://")

# Create async engine with optimized settings
engine = create_async_engine(
    database_url,
    pool_size=10,            # Number of connections to maintain
    max_overflow=20,         # Additional connections when needed
    pool_pre_ping=True,      # Validate connections before use
    pool_recycle=300,        # Recycle connections every 5 minutes
    echo=settings.DEBUG,     # Log SQL queries in debug mode
    echo_pool=settings.DEBUG # Log connection pool events in debug mode
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# Create base class for models
Base = declarative_base()

# Async database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Database health check
async def check_database_health() -> Dict[str, Any]:
    """Check database connection and return health status"""
    try:
        async with AsyncSessionLocal() as session:
            # Simple health check query
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            
            # Get connection pool status
            pool = engine.pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }
            
            logger.info("Database health check passed", pool_status=pool_status)
            
            return {
                "healthy": True,
                "pool_status": pool_status,
                "connection": "active"
            }
            
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "healthy": False,
            "error": str(e),
            "connection": "failed"
        }

# Database initialization
async def init_database():
    """Initialize database tables"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database tables", error=str(e))
        raise