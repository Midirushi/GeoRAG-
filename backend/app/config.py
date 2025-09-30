from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()  # 加载.env文件

class Settings(BaseSettings):
    # 数据库配置
    POSTGRES_URL: str = "postgresql+asyncpg://postgres:123456@localhost:5432/spatiotemporal_rag"
    QDRANT_URL: str = "http://localhost:6333"
    REDIS_URL: str = "redis://localhost:6379/0"
    # LLM配置
    OPENAI_API_KEY: str  # 从.env读取
    ANTHROPIC_API_KEY: str  # 从.env读取
    LLM_MODEL: str = "claude-sonnet-4-5"  # 默认LLM模型
    EMBEDDING_MODEL: str = "text-embedding-3-large"  # 默认Embedding模型
    # API配置
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list = ["http://localhost:3000"]  # 前端地址

settings = Settings()