# app/models/request.py（请求体模型）
from pydantic import BaseModel
from typing import Optional, List, Dict, Union
from datetime import datetime

class GeoFilter(BaseModel):
    """地理过滤条件"""
    lat: float  # 纬度
    lon: float  # 经度
    radius_km: Optional[float] = 10  # 半径（默认10km）
    address: Optional[str] = None  # 地址描述

class TimeFilter(BaseModel):
    """时间过滤条件"""
    start: Union[int, str]  # 开始时间（Unix时间戳或字符串）
    end: Union[int, str]  # 结束时间（Unix时间戳或字符串）
    precision: Optional[str] = "year"  # 时间精度
    display_time: Optional[str] = None  # 展示用时间（如“明朝(1368-1644)”）

class QueryIntent(BaseModel):
    """查询意图（内部使用）"""
    original_query: str  # 原始查询
    semantic_query: str  # 改写后的语义查询
    intent_type: str  # 意图类型
    keywords: List[str]  # 关键词
    category: Optional[str] = None  # 分类
    geo_filter: Optional[GeoFilter] = None  # 地理过滤
    time_filter: Optional[TimeFilter] = None  # 时间过滤
    embedding: Optional[List[float]] = None  # 查询向量

class QueryRequest(BaseModel):
    """问答查询请求"""
    query: str  # 用户问题
    filters: Optional[Dict] = None  # 过滤条件（geo/time/category）
    options: Optional[Dict] = None  # 选项（top_k/stream/include_sources）

