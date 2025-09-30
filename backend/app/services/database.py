from sqlalchemy import create_engine, Column, UUID, String, Text, Float, TIMESTAMP, ARRAY, Boolean, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import uuid
from datetime import datetime

# 异步引擎
async_engine = create_async_engine(settings.POSTGRES_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()

# 知识条目主表
class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    category = Column(ARRAY(String(100)), nullable=True)
    tags = Column(ARRAY(String(100)), nullable=True)
    source = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

# 地理信息表（PostGIS）
class GeoLocation(Base):
    __tablename__ = "geo_locations"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID, nullable=False)  # 关联知识条目ID
    geom = Column("geom", "Geometry(Point, 4326)", nullable=True)  # 点坐标（WGS84）
    geom_area = Column("geom_area", "Geometry(Polygon, 4326)", nullable=True)  # 区域范围
    address = Column(Text, nullable=True)
    country = Column(String(100), nullable=True)
    province = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)

# 时间信息表
class TemporalInfo(Base):
    __tablename__ = "temporal_info"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID, nullable=False)  # 关联知识条目ID
    start_time = Column(TIMESTAMP, nullable=True)
    end_time = Column(TIMESTAMP, nullable=True)
    time_precision = Column(String(20), nullable=True)  # day/month/year/decade
    is_historical = Column(Boolean, default=False)
    dynasty = Column(String(50), nullable=True)  # 历史朝代
    era = Column(String(100), nullable=True)

# 查询历史表
class QueryHistory(Base):
    __tablename__ = "query_history"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, nullable=True)
    query = Column(Text, nullable=False)
    query_type = Column(String(50), nullable=True)
    geo_filter = Column("geo_filter", "Geometry(Polygon, 4326)", nullable=True)
    time_filter = Column(JSONB, nullable=True)
    results_count = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

# 数据库依赖（供接口调用）
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# 初始化表结构（首次运行）
async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)