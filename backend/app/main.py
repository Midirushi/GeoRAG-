from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from app.services.rag_service import RAGService
from app.api.query import router as query_router
from app.config import settings

# 全局RAG服务实例（生命周期管理）
rag_service = RAGService()

# 生命周期管理：启动/关闭时初始化/清理服务
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化RAG服务
    await rag_service.initialize()
    app.state.rag_service = rag_service  # 绑定到app状态，供依赖注入使用
    yield
    # 关闭时清理资源
    await rag_service.cleanup()

# 创建FastAPI应用
app = FastAPI(
    title="时空地理知识库RAG API",
    description="基于RAG的时空地理知识问答与检索系统",
    version="1.0.0",
    lifespan=lifespan,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs"  # Swagger文档地址
)

# 配置CORS（允许前端跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)

# 挂载API路由
app.include_router(query_router)

# 启动服务（本地开发用）
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # 允许外部访问
        port=8000,       # 端口
        reload=True,     # 开发模式：代码修改自动重启
        workers=1        # 生产环境可增加workers数量
    )