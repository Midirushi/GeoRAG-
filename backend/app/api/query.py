from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from app.models.request import QueryRequest
from app.models.response import QueryResponse
from app.services.rag_service import RAGService
from app.config import settings

# 创建路由（前缀：/api/v1）
router = APIRouter(prefix=settings.API_PREFIX)

# 依赖注入：获取RAG服务（需在main.py中初始化）
def get_rag_service() -> RAGService:
    from app.main import app  # 避免循环导入
    if not hasattr(app.state, "rag_service"):
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    return app.state.rag_service

@router.post("/query", response_model=QueryResponse, summary="非流式问答查询")
async def query(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    非流式问答查询：
    - 接收用户问题和过滤条件（地理/时间/分类）
    - 返回完整回答、来源列表、查询耗时
    """
    try:
        return await rag_service.query(
            query=request.query,
            filters=request.filters,
            options=request.options
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query/stream", summary="流式问答查询")
async def query_stream(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
) -> StreamingResponse:
    """
    流式问答查询：
    - 先返回来源信息，再逐段返回回答（SSE格式）
    - 适合长回答场景，提升用户体验
    """
    async def stream_generator() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in rag_service.query_stream(
                query=request.query,
                filters=request.filters,
                options=request.options
            ):
                yield chunk.encode("utf-8")
        except Exception as e:
            yield f'{{"type":"error","data":"{str(e)}"}}\n'.encode("utf-8")
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )

@router.get("/search", summary="条件检索（非问答）")
async def search(
    keywords: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_km: Optional[float] = 10,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    category: Optional[str] = None,
    limit: Optional[int] = 20,
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    条件检索：
    - 支持关键词、地理范围、时间范围、分类过滤
    - 返回符合条件的知识条目列表（非生成式回答）
    """
    # 构建过滤条件
    filters = {
        "keywords": keywords.split(",") if keywords else None,
        "geo": {"lat": lat, "lon": lon, "radius_km": radius_km} if lat and lon else None,
        "time": {"start": start_time, "end": end_time} if start_time or end_time else None,
        "category": category
    }
    try:
        # 调用检索服务（需在RAGService中实现search方法）
        return await rag_service.search(filters=filters, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))