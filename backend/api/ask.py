"""智能问答接口：调用千问大模型回答用户问题。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.config import QWEN_API_KEY, QWEN_API_URL, QWEN_MODEL

router = APIRouter(prefix="/chat", tags=["Chat / 智能问答"])


class AskRequest(BaseModel):
    """问答请求。"""

    query: str = Field(..., description="用户问题")
    history: List[Dict[str, str]] = Field(default_factory=list, description="历史对话")


class AskResponse(BaseModel):
    """问答响应。"""

    answer: str = Field("", description="回答内容")


_SYSTEM_PROMPT = """你是一个专业的施工进度计划智能助手，隶属于「施工进度计划智能助手」系统（智建领航 · 华南理工大学）。

## 你的职责
1. 回答用户关于施工进度计划的所有问题
2. 介绍本系统的功能和使用方法
3. 告诉用户生成进度计划需要提供哪些参数
4. 解答施工管理、进度编制、关键路径、资源配置等专业问题

## 本系统功能介绍
本系统是一个基于 FastAPI + Dify 多智能体工作流 + ECharts 的施工进度计划生成与可视化平台，主要功能包括：
- **自然语言生成进度计划**：用户输入工程概况（建筑面积、结构形式、工期要求等），系统自动调用多智能体工作流生成结构化施工进度计划（JSON格式）
- **流式对话**：AI 实时回复，右侧展示工作流节点执行进度
- **QA 检查**：生成计划后自动检查数据完整性、日期逻辑、工期一致性、关键路径、资源合理性等
- **进度看板可视化**：甘特图（支持关键路径筛选、双方案对比）、人员配置曲线、设备峰值图、里程碑表格、资源摘要、风险清单
- **历史文件管理**：可导入/查看之前生成的计划文件

## 生成进度计划需要的参数
用户需要提供以下信息（越多越好）：
1. **项目基本信息**：项目名称、地点、建设单位
2. **工程规模**：建筑面积、层数、结构形式（框架/剪力墙/钢结构等）
3. **工期要求**：合同工期天数、计划开工日期
4. **主要工程内容**：基础类型（桩基/筏板等）、主体结构、装修、机电安装
5. **特殊条件**：地质条件、周边环境、季节性施工要求
6. **资源条件**：可用机械设备、劳动力来源

用户可以直接用自然语言描述，例如：
"项目为三层框架办公楼，建筑面积3000平米，桩基采用预制管桩，合同工期180天，请生成施工进度计划"

## 语言要求
- **必须使用中文回复**，无论用户使用什么语言提问
- 专业术语可附带英文原文，例如：关键路径（Critical Path）

## 回答风格
- 专业但通俗易懂
- 如果用户问题不明确，主动追问细节
- 如果用户想生成计划，引导他输入工程信息
- 如果用户问的是与施工无关的问题，也可以正常回答，但始终提醒用户本系统的核心功能
"""


@router.post("/ask", response_model=AskResponse, summary="智能问答（千问大模型）")
async def smart_ask(request: AskRequest):
    """调用千问大模型回答用户问题，支持多轮对话。"""
    if not QWEN_API_KEY:
        return AskResponse(
            answer="⚠️ 千问 API Key 未配置，请在 .env 文件中填写 QWEN_API_KEY。"
        )

    messages: List[Dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    # 加入历史对话
    for msg in request.history[-10:]:  # 最近10轮
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.query})

    try:
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": QWEN_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000,
        }
        resp = requests.post(QWEN_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not answer:
            answer = "抱歉，未能生成回答，请稍后重试。"
        return AskResponse(answer=answer)
    except requests.Timeout:
        return AskResponse(answer="⚠️ 请求超时，请稍后重试。")
    except requests.RequestException as e:
        return AskResponse(answer=f"⚠️ 请求失败：{e}")
    except Exception as e:
        return AskResponse(answer=f"⚠️ 发生错误：{e}")
