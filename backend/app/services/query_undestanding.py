from typing import Dict, Optional, List
from datetime import datetime
import json
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from app.config import settings
from app.models.request import QueryIntent, GeoFilter, TimeFilter
from app.utils.geo_parser import GeoParser  # 后续实现地理解析工具
from app.utils.time_parser import TimeParser  # 后续实现时间解析工具

class QueryUnderstandingService:
    def __init__(self):
        self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.geo_parser = GeoParser()  # 地理实体识别与编码
        self.time_parser = TimeParser()  # 时间表达式标准化
        self.embedding_model = settings.EMBEDDING_MODEL

    async def parse(self, query: str, filters: Optional[Dict] = None) -> QueryIntent:
        """解析用户查询，返回结构化意图（含地理/时间过滤、语义向量）"""
        # 1. 用LLM提取结构化信息（意图类型、关键词、分类等）
        structured_info = await self._extract_with_llm(query)
        # 2. 解析地理过滤条件（优先用用户传入的filters，其次从查询文本提取）
        geo_filter = await self._parse_geo_filter(query, filters)
        # 3. 解析时间过滤条件（同上）
        time_filter = self._parse_time_filter(query, filters)
        # 4. 生成查询文本的向量（用于后续向量检索）
        query_embedding = await self._generate_embedding(structured_info["semantic_query"])
        
        # 封装为QueryIntent对象（Pydantic模型）
        return QueryIntent(
            original_query=query,
            semantic_query=structured_info["semantic_query"],
            intent_type=structured_info["intent_type"],
            keywords=structured_info["keywords"],
            category=structured_info["category"],
            geo_filter=geo_filter,
            time_filter=time_filter,
            embedding=query_embedding
        )

    async def _extract_with_llm(self, query: str) -> Dict:
        """用Anthropic LLM提取查询的结构化信息（意图、关键词等）"""
        prompt = f"""请分析用户查询，提取以下结构化信息（严格按JSON格式返回，无额外文本）：
        用户查询：{query}
        返回格式要求：
        {{
            "semantic_query": "改写为更适合语义检索的查询（如补充上下文）",
            "intent_type": "查询意图类型（fact_query=事实查询/comparison=对比/explanation=解释/exploration=探索）",
            "keywords": ["核心关键词1", "核心关键词2"],
            "category": "知识分类（历史/地理/文化/建筑等，无则填null）",
            "geo_hints": ["查询中提到的地名（无则填[]）"],
            "time_hints": ["查询中提到的时间表达（无则填[]）"]
        }}
        """
        # 调用Anthropic API
        response = await self.anthropic_client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        # 解析JSON响应（容错处理）
        try:
            return json.loads(response.content[0].text.strip())
        except Exception as e:
            print(f"⚠️ LLM response parse error: {e}")
            # 失败时返回默认值
            return {
                "semantic_query": query,
                "intent_type": "fact_query",
                "keywords": query.split(),
                "category": None,
                "geo_hints": [],
                "time_hints": []
            }

    async def _parse_geo_filter(self, query: str, filters: Optional[Dict]) -> Optional[GeoFilter]:
        """解析地理过滤条件：优先用用户传入的filters，否则从查询文本提取"""
        if filters and filters.get("geo"):
            # 用户已指定地理过滤（如地图选择的范围）
            return GeoFilter(**filters["geo"])
        # 从查询文本提取地名并地理编码（如“北京故宫”→经纬度）
        geo_entities = self.geo_parser.extract(query)  # 提取地名（需实现GeoParser）
        if not geo_entities:
            return None
        # 地理编码（调用高德/百度地图API，此处简化为示例）
        first_geo = geo_entities[0]
        coords = await self.geo_parser.geocode(first_geo)  # 地名→(lat, lon)
        if not coords:
            return None
        # 返回GeoFilter（默认半径10km，可根据需求调整）
        return GeoFilter(
            lat=coords["lat"],
            lon=coords["lon"],
            radius_km=10,
            address=first_geo
        )

    def _parse_time_filter(self, query: str, filters: Optional[Dict]) -> Optional[TimeFilter]:
        """解析时间过滤条件：优先用用户传入的filters，否则从查询文本提取"""
        if filters and filters.get("time"):
            # 用户已指定时间范围（如时间轴选择）
            return TimeFilter(**filters["time"])
        # 从查询文本提取时间表达并标准化（如“明朝”→1368-1644）
        time_entities = self.time_parser.extract(query)  # 提取时间（需实现TimeParser）
        if not time_entities:
            return None
        # 时间标准化（如“明朝”→{"start": 1368, "end": 1644, "precision": "year"}）
        normalized_time = self.time_parser.normalize(time_entities[0])
        if not normalized_time:
            return None
        # 转换为Unix时间戳（便于数据库过滤）
        return TimeFilter(
            start=normalized_time["start_timestamp"],
            end=normalized_time["end_timestamp"],
            precision=normalized_time["precision"],
            display_time=normalized_time["display"]  # 用于前端展示（如“明朝(1368-1644)”）
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """用OpenAI Embedding模型生成文本向量"""
        response = await self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text.strip()
        )
        return response.data[0].embedding