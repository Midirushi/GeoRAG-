from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, 
    Range, GeoRad, GeoPoint
)
from typing import List, Dict, Optional
import uuid
from app.config import settings

class VectorStore:
    def __init__(self):
        self.client: AsyncQdrantClient = None
        self.collection_name = "spatiotemporal_knowledge"  # 向量集合名
        self.embedding_dim = 1536  # text-embedding-3-large的维度（根据模型调整）

    async def connect(self):
        """连接Qdrant并创建集合（不存在时）"""
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)
        # 检查集合是否存在
        collections = await self.client.get_collections()
        if self.collection_name not in [c.name for c in collections.collections]:
            await self._create_collection()
        print("✅ Qdrant connected")

    async def _create_collection(self):
        """创建向量集合（含地理/时间字段索引）"""
        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.embedding_dim,
                distance=Distance.COSINE  # 余弦相似度
            )
        )
        # 为地理、时间、分类字段创建索引（加速过滤）
        await self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="geo_point",
            field_schema="geo"
        )
        await self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="start_time",
            field_schema="integer"
        )
        await self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="category",
            field_schema="keyword"
        )
        print(f"✅ Qdrant collection '{self.collection_name}' created")

    async def insert(self, documents: List[Dict]):
        """插入文档到Qdrant（需包含embedding、geo、temporal等字段）"""
        if not self.client:
            raise Exception("Qdrant client not connected")
        
        points = []
        for doc in documents:
            # 构建Qdrant点结构（ID+向量+元数据）
            point = PointStruct(
                id=str(uuid.uuid4()),  # 自定义ID（或用默认）
                vector=doc["embedding"],  # 文档向量
                payload={
                    "entry_id": str(doc["id"]),  # 关联PostgreSQL知识条目ID
                    "title": doc["title"],
                    "content": doc["content"],
                    "category": doc["metadata"]["category"],
                    "tags": doc["metadata"]["tags"],
                    # 地理信息（格式：{"lat": 纬度, "lon": 经度}）
                    "geo_point": {
                        "lat": doc["geo"]["coordinates"][1],
                        "lon": doc["geo"]["coordinates"][0]
                    } if doc.get("geo") else None,
                    # 时间信息（Unix时间戳，便于范围过滤）
                    "start_time": doc["temporal"]["start_timestamp"],
                    "end_time": doc["temporal"]["end_timestamp"],
                    "metadata": doc["metadata"]
                }
            )
            points.append(point)
        
        # 批量插入
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print(f"✅ Inserted {len(points)} documents into Qdrant")

    async def search(
        self,
        query_vector: List[float],
        geo_filter: Optional[Dict] = None,  # {"lat": 39.917, "lon": 116.397, "radius_km": 5}
        time_filter: Optional[Dict] = None,  # {"start": 1368000000, "end": 1644000000}（Unix时间戳）
        category_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """向量检索（支持地理、时间、分类过滤）"""
        if not self.client:
            raise Exception("Qdrant client not connected")
        
        # 构建过滤条件
        filter_conditions = []
        # 1. 地理过滤（半径范围）
        if geo_filter:
            filter_conditions.append(
                FieldCondition(
                    key="geo_point",
                    geo_radius=GeoRad(
                        center=GeoPoint(
                            lat=geo_filter["lat"],
                            lon=geo_filter["lon"]
                        ),
                        radius=geo_filter["radius_km"] * 1000  # 转换为米
                    )
                )
            )
        # 2. 时间过滤（范围）
        if time_filter:
            filter_conditions.append(
                FieldCondition(
                    key="start_time",
                    range=Range(
                        gte=time_filter["start"],  # 大于等于开始时间
                        lte=time_filter.get("end", float("inf"))  # 小于等于结束时间（默认无穷大）
                    )
                )
            )
        # 3. 分类过滤（精确匹配）
        if category_filter:
            filter_conditions.append(
                FieldCondition(
                    key="category",
                    match={"value": category_filter}
                )
            )
        
        # 执行检索
        search_filter = Filter(must=filter_conditions) if filter_conditions else None
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=limit,
            with_payload=True  # 返回元数据
        )
        
        # 格式化结果（提取ID、得分、元数据）
        return [
            {
                "id": result.id,
                "score": result.score,  # 相似度得分
                "payload": result.payload  # 元数据（标题、地理、时间等）
            }
            for result in results
        ]

    async def close(self):
        """关闭Qdrant连接"""
        if self.client:
            await self.client.close()
            print("✅ Qdrant connection closed")