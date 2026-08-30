"""FastAPI 后端配置。

优先从环境变量 / .env 读取；未设置时回退到项目根目录的 config.py，
保证原有 Streamlit 应用和后端可以共用同一套密钥。
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env（如果存在）
_env_path = Path(__file__).resolve().parent.parent / ".env"
_env_example = Path(__file__).resolve().parent.parent / ".env.example"
if _env_path.exists():
    load_dotenv(_env_path)
elif _env_example.exists():
    load_dotenv(_env_example)

BASE_DIR = Path(__file__).resolve().parent.parent

# ---- Dify 主工作流（生成进度计划）----
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_CHATFLOW_URL = os.getenv(
    "DIFY_CHATFLOW_URL",
    "https://api.dify.ai/v1/chat-messages",
)
DIFY_TIMEOUT = int(os.getenv("DIFY_TIMEOUT", "1800"))
DIFY_MAX_RETRIES = int(os.getenv("DIFY_MAX_RETRIES", "3"))
DIFY_RETRY_INTERVAL = int(os.getenv("DIFY_RETRY_INTERVAL", "3"))

# ---- QA Agent（计划质量检查）----
# 1) 如果使用 Dify Workflow/Agent：填 API Key 和接口地址
# 2) 如果只想用本地规则检查：保持为空，后端会回退到本地 QA
DIFY_QA_API_KEY = os.getenv("DIFY_QA_API_KEY", "")
DIFY_QA_URL = os.getenv("DIFY_QA_URL", "")
# QA 工作流类型：chatflow | workflow | agent
DIFY_QA_TYPE = os.getenv("DIFY_QA_TYPE", "chatflow")

# ---- 示例项目与本机历史 ----
DEMO_PLAN_PATH = Path(os.getenv("DEMO_PLAN_PATH", BASE_DIR / "名创优品.json"))
HISTORY_DIR = Path(os.getenv("HISTORY_DIR", BASE_DIR / "uploaded_history"))
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# ---- CORS / 服务 ----
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# ---- 运行模式 ----
DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

# ---- 千问问答模型（智能助手）----
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3.8-flash")
QWEN_API_URL = os.getenv("QWEN_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
