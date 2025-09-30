from typing import List, Dict, AsyncGenerator
from datetime import datetime
import asyncio
from app.services.query_understanding import QueryUnderstandingService
from app.services.retriever import HybridRetriever
from app.services.generator import LLMGenerator
from app.services.vector_store import VectorStore
from app.services.database import get_db, QueryHistory
from app.models.request import QueryRequest, QueryIntent
from app.models.response import QueryResponse, Source

class RAGService:
    def __init__(self):
        self.query_understanding: QueryUnderstandingService = None
        self.retriever: HybridRetriever = None
        self.generator: LLMGenerator = None
        self.vector_store: VectorStore = None

    async def initialize(self):
        """初始化所有服务组件（启动时调用）"""
        # 1. 初始化向量库
        self.vector_store = VectorStore()
        await self.vector_store.connect()
        # 2. 初始化核心服务
        self.query_understanding = QueryUnderstandingService()
        self.retriever = HybridRetriever(self.vector_store)
        self.generator = LLMGenerator()
        print("✅ RAG Service initialized")

    async def cleanup(self):
        """清理资源（关闭时调用）"""
        if self.vector_store:
            await self.vector_store.close()
        print("✅ RAG Service cleaned up")

    async def query(self, query: str, filters: Optional[Dict] = None, options: Optional[Dict] = None) -> QueryResponse:
        """非流式查询：完整返回回答+来源"""
        start_time = datetime.utcnow()
        # 1. 解析查询意图
        query_intent = await self.query_understanding.parse(query, filters)
        # 2. 混合检索（默认取Top5结果）
        top_k = options.get("top_k", 5) if options else 5
        contexts = await self.retriever.retrieve(query_intent, top_k)
        if not contexts:
            return QueryResponse(
                answer="未找到相关时空地理知识，无法回答该问题。",
                sources=[],
                query_time_ms=0,
                model_used=self.generator.model
            )
        # 3. 生成回答
        answer = await self.generator.generate(query, contexts)
        # 4. 格式化来源信息
        sources = self._format_sources(contexts)
        # 5. 计算查询耗时
        query_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        # 6. 异步记录查询历史
        asyncio.create_task(self._log_query(query, query_intent, len(sources), query_time_ms))
        # 7. 返回结果
        return QueryResponse(
            answer=answer,
            sources=sources,
            query_time_ms=round(query_time_ms, 2),
            model_used=self.generator.model
        )

    async def query_stream(self, query: str, filters: Optional[Dict] = None, options: Optional[Dict] = None) -> AsyncGenerator[str, None]:
        """流式查询：先返回来源，再逐段返回回答"""
        # 1. 解析查询意图
        query_intent = await self.query_understanding.parse(query, filters)
        # 2. 混合检索
        top_k = options.get("top_k", 5) if options else 5
        contexts = await self.retriever.retrieve(query_intent, top_k)
        # 3. 先返回来源信息（JSON格式）
        sources = self._format_sources(contexts)
        yield f'{{"type":"sources","data":{sources}}}\n'
        # 4. 若无上下文，返回无结果提示
        if not contexts:
            yield f'{{"type":"content","data":"未找到相关时空地理知识，无法回答该问题。"}}\n'
            yield '{"type":"done"}\n'
            return
        # 5. 流式生成回答（逐段返回）
        async for chunk in self.generator.generate_stream(query, contexts):
            yield f'{{"type":"content","data":"{chunk.replace('"', '\\"')}"}}\n'
        # 6. 发送完成信号
        yield '{"type":"done"}\n'
        # 7. 异步记录查询历史
        asyncio.create_task(self._log_query(query, query_intent, len(contexts), 0))

    def _format_sources(self, contexts: List[Dict]) -> List[Source]:
        """格式化来源信息（适配前端展示）"""
        sources = []
        for ctx in contexts:
            payload = ctx["payload"]
            sources.append(Source(
                id=payload["entry_id"],
                title=payload.get("title", "未知标题"),
                snippet=payload.get("content", "")[:200] + "..." if len(payload.get("content", "")) > 200 else payload.get("content", ""),
                geo={
                    "location": [payload.get("geo_point", {}).get("lon"), payload.get("geo_point", {}).get("lat")] if payload.get("geo_point") else None,
                    "address": payload.get("geo_point", {}).get("address", "未知地点")
                },
                temporal={
                    "period": payload.get("metadata", {}).get("display_time", "未知时间")
                },
                relevance_score=round(ctx["score"], 4)
            ))
        return sources

    async def _log_query(self, query: str, intent: QueryIntent, results_count: int, query_time_ms: float):
        """记录查询历史到数据库"""
        db = await anext(get_db())
        try:
            # 构建地理过滤的Polygon（简化为中心点周围的正方形）
            geo_filter_geom = None
            if intent.geo_filter:
                lat = intent.geo_filter.lat
                lon = intent.geo_filter.lon
                radius_km = intent.geo_filter.radius_km
                # 转换为经纬度范围（1km≈0.009°）
                delta = radius_km * 0.009
                # 构建正方形Polygon（WGS84坐标系）
                geo_filter_geom = func.ST_MakePolygon(
                    func.ST_MakeLine([
                        func.ST_SetSRID(func.ST_MakePoint(lon - delta, lat - delta), 4326),
                        func.ST_SetSRID(func.ST_MakePoint(lon + delta, lat - delta), 4326),
                        func.ST_SetSRID(func.ST_MakePoint(lon + delta, lat + delta), 4326),
                        func.ST_SetSRID(func.ST_MakePoint(lon - delta, lat + delta), 4326),
                        func.ST_SetSRID(func.ST_MakePoint(lon - delta, lat - delta), 4326)
                    ])
                )
            # 记录查询历史
            history = QueryHistory(
                query=query,
                query_type=intent.intent_type,
                geo_filter=geo_filter_geom,
                time_filter={
                    "start": intent.time_filter.start if intent.time_filter else None,
                    "end": intent.time_filter.end if intent.time_filter else None,
                    "precision": intent.time_filter.precision if intent.time_filter else None
                },
                results_count=results_count,
                created_at=datetime.utcnow()
            )
            db.add(history)
            await db.commit()
        except Exception as e:
            print(f"⚠️ Failed to log query: {e}")
            await db.rollback()
        finally:
            await db.close()