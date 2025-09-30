from typing import List, Dict, Optional
from app.services.vector_store import VectorStore
from app.services.database import get_db, KnowledgeEntry, GeoLocation, TemporalInfo
from app.models.request import QueryIntent
from sqlalchemy.future import select
from sqlalchemy import func
import asyncio

class HybridRetriever:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store  # Qdrant向量库
        self.alpha = 0.6  # 语义相似度权重
        self.beta = 0.3   # 地理相关性权重
        self.gamma = 0.1  # 时间相关性权重

    async def retrieve(self, query_intent: QueryIntent, top_k: int = 10) -> List[Dict]:
        """混合检索：向量检索 + 地理检索 + 时间检索 + 重排序"""
        # 1. 并行执行向量检索和数据库过滤（提升效率）
        vector_task = self._vector_retrieval(query_intent, top_k * 2)  # 多取2倍结果用于重排序
        db_task = self._db_retrieval(query_intent, top_k * 2)
        vector_results, db_results = await asyncio.gather(vector_task, db_task)
        
        # 2. 合并结果（去重，保留所有唯一条目）
        merged_results = self._merge_results(vector_results, db_results)
        if not merged_results:
            return []
        
        # 3. 重排序（基于语义、地理、时间三维度评分）
        reranked_results = self._rerank(merged_results, query_intent)
        
        # 4. 返回Top-K结果
        return reranked_results[:top_k]

    async def _vector_retrieval(self, query_intent: QueryIntent, limit: int) -> List[Dict]:
        """向量检索（Qdrant）：语义相似度 + 地理/时间过滤"""
        # 构建地理过滤参数（转换为Qdrant格式）
        geo_filter = None
        if query_intent.geo_filter:
            geo_filter = {
                "lat": query_intent.geo_filter.lat,
                "lon": query_intent.geo_filter.lon,
                "radius_km": query_intent.geo_filter.radius_km
            }
        # 构建时间过滤参数（Unix时间戳）
        time_filter = None
        if query_intent.time_filter:
            time_filter = {
                "start": query_intent.time_filter.start,
                "end": query_intent.time_filter.end
            }
        # 调用Qdrant检索
        return await self.vector_store.search(
            query_vector=query_intent.embedding,
            geo_filter=geo_filter,
            time_filter=time_filter,
            category_filter=query_intent.category,
            limit=limit
        )

    async def _db_retrieval(self, query_intent: QueryIntent, limit: int) -> List[Dict]:
        """数据库检索（PostgreSQL+PostGIS）：地理空间查询 + 时间范围查询"""
        db = await anext(get_db())  # 获取数据库会话
        try:
            # 1. 构建查询（关联知识条目、地理、时间表）
            query = select(
                KnowledgeEntry, GeoLocation, TemporalInfo
            ).outerjoin(
                GeoLocation, KnowledgeEntry.id == GeoLocation.entry_id
            ).outerjoin(
                TemporalInfo, KnowledgeEntry.id == TemporalInfo.entry_id
            )
            
            # 2. 添加地理过滤（PostGIS空间查询：距离中心点一定范围）
            if query_intent.geo_filter:
                lat = query_intent.geo_filter.lat
                lon = query_intent.geo_filter.lon
                radius_km = query_intent.geo_filter.radius_km
                # PostGIS函数：ST_DWithin（判断点是否在半径范围内，单位：米）
                query = query.where(
                    func.ST_DWithin(
                        GeoLocation.geom,
                        func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326),
                        radius_km * 1000
                    )
                )
            
            # 3. 添加时间过滤（时间范围匹配）
            if query_intent.time_filter:
                start = query_intent.time_filter.start
                end = query_intent.time_filter.end
                query = query.where(
                    TemporalInfo.start_time <= end,
                    TemporalInfo.end_time >= start
                )
            
            # 4. 添加分类过滤
            if query_intent.category:
                query = query.where(
                    KnowledgeEntry.category.any(query_intent.category)
                )
            
            # 5. 执行查询并限制结果数
            result = await db.execute(query.limit(limit))
            rows = result.all()
            
            # 6. 格式化结果（与向量检索结果结构对齐）
            formatted = []
            for entry, geo, temporal in rows:
                formatted.append({
                    "id": str(entry.id),
                    "score": 0.0,  # 数据库检索无初始得分，后续重排序计算
                    "payload": {
                        "entry_id": str(entry.id),
                        "title": entry.title,
                        "content": entry.content,
                        "category": entry.category,
                        "tags": entry.tags,
                        "geo_point": {
                            "lat": func.ST_Y(geo.geom).scalar() if geo and geo.geom else None,
                            "lon": func.ST_X(geo.geom).scalar() if geo and geo.geom else None
                        },
                        "start_time": temporal.start_time.timestamp() if temporal and temporal.start_time else None,
                        "end_time": temporal.end_time.timestamp() if temporal and temporal.end_time else None,
                        "metadata": {
                            "source": entry.source,
                            "confidence": entry.confidence,
                            "display_time": f"{temporal.dynasty}({temporal.start_time.year}-{temporal.end_time.year})" 
                            if temporal and temporal.dynasty else None
                        }
                    }
                })
            return formatted
        finally:
            await db.close()

    def _merge_results(self, vector_results: List[Dict], db_results: List[Dict]) -> List[Dict]:
        """合并向量检索和数据库检索结果（去重，保留语义得分）"""
        merged = {}
        # 先添加向量检索结果（保留语义得分）
        for res in vector_results:
            entry_id = res["payload"]["entry_id"]
            merged[entry_id] = res
        # 再添加数据库检索结果（无得分则保留，有则取最高）
        for res in db_results:
            entry_id = res["payload"]["entry_id"]
            if entry_id not in merged:
                merged[entry_id] = res
        # 返回去重后的列表
        return list(merged.values())

    def _rerank(self, results: List[Dict], query_intent: QueryIntent) -> List[Dict]:
        """重排序：综合语义相似度、地理相关性、时间相关性计算最终得分"""
        for res in results:
            # 1. 语义相似度得分（向量检索结果已有，数据库结果默认为0.5）
            semantic_score = res["score"] if res["score"] > 0 else 0.5
            
            # 2. 地理相关性得分（0-1，距离越近得分越高）
            geo_score = 1.0
            if query_intent.geo_filter and res["payload"]["geo_point"]:
                query_lat = query_intent.geo_filter.lat
                query_lon = query_intent.geo_filter.lon
                res_lat = res["payload"]["geo_point"]["lat"]
                res_lon = res["payload"]["geo_point"]["lon"]
                # 计算两点距离（简化为曼哈顿距离，实际可用Haversine公式）
                distance_km = abs(query_lat - res_lat) * 111 + abs(query_lon - res_lon) * 111
                # 距离越近得分越高（超过radius_km则得0）
                max_distance = query_intent.geo_filter.radius_km
                geo_score = max(0.0, 1.0 - (distance_km / max_distance))
            
            # 3. 时间相关性得分（0-1，重叠时间越长得分越高）
            time_score = 1.0
            if query_intent.time_filter and res["payload"]["start_time"] and res["payload"]["end_time"]:
                query_start = query_intent.time_filter.start
                query_end = query_intent.time_filter.end
                res_start = res["payload"]["start_time"]
                res_end = res["payload"]["end_time"]
                # 计算时间重叠比例
                overlap_start = max(query_start, res_start)
                overlap_end = min(query_end, res_end)
                if overlap_end <= overlap_start:
                    time_score = 0.0
                else:
                    overlap_duration = overlap_end - overlap_start
                    query_duration = query_end - query_start
                    time_score = overlap_duration / query_duration
            
            # 4. 计算最终得分（加权求和）
            final_score = (
                self.alpha * semantic_score +
                self.beta * geo_score +
                self.gamma * time_score
            )
            res["score"] = final_score
        
        # 按最终得分降序排序
        return sorted(results, key=lambda x: x["score"], reverse=True)