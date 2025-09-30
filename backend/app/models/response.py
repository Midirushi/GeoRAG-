# app/models/response.py（响应体模型）
from pydantic import BaseModel
from typing import Optional, List, Dict

class Source(BaseModel):
    """回答来源信息"""
    id: str  # 知识条目ID
    title: str  # 标题
    snippet: str  # 内容片段
    geo: Dict[str, Optional[Union[str, List[float]]]]  # 地理信息
    temporal: Dict[str, Optional[str]]  # 时间信息
    relevance_score: float  # 相关性得分

class QueryResponse(BaseModel):
    """问答查询响应"""
    answer: str  # 回答内容
    sources: List[Source]  # 来源列表
    query_time_ms: float  # 查询耗时（毫秒）
    model_used: str  # 使用的LLM模型