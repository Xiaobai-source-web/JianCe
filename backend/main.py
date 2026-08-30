"""FastAPI 后端入口。

把原 Streamlit 一体化应用拆分为独立后端：
- 聊天 / 生成计划：/api/v1/chat/*
- 计划处理：/api/v1/plan/*
- 历史文件：/api/v1/history/*
- 文件上传：/api/v1/upload/*
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import ask, chat, history, plan, upload
from backend.config import CORS_ORIGINS, DEBUG, PORT


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动/关闭生命周期。"""
    print(f"🚀 FastAPI 后端启动：http://0.0.0.0:{PORT}")
    yield
    print("👋 FastAPI 后端关闭")


app = FastAPI(
    title="施工进度计划智能助手 API",
    description="基于 FastAPI + Dify 的进度计划生成与 QA 检查后端",
    version="1.0.0",
    debug=DEBUG,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api/v1")
app.include_router(ask.router, prefix="/api/v1")
app.include_router(plan.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")

# 托管前端静态文件
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    """前端首页。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", summary="健康检查")
def health():
    from backend.config import DIFY_API_KEY, DIFY_CHATFLOW_URL
    return {
        "status": "ok",
        "service": "progress-plan-api",
        "dify": {
            "configured": bool(DIFY_API_KEY),
            "base_url": DIFY_CHATFLOW_URL,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=DEBUG)
