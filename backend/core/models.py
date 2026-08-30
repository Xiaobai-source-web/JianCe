"""Pydantic 数据模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天/生成计划请求。"""

    query: str = Field(..., description="用户输入的提示词")
    conversation_id: Optional[str] = Field(None, description="Dify 会话 ID，续问时传入")
    current_plan_json: Optional[Dict[str, Any]] = Field(None, description="当前已有计划数据，用于调整/优化")
    run_qa: bool = Field(False, description="是否在生成后自动调用 QA Agent 检查")


class ChatResponse(BaseModel):
    """非流式聊天响应。"""

    answer: str = Field("", description="AI 给用户的文字说明")
    plan: Dict[str, Any] = Field(default_factory=dict, description="解析后的进度计划 JSON")
    conversation_id: Optional[str] = Field(None, description="Dify 会话 ID")
    qa_report: Optional[Dict[str, Any]] = Field(None, description="若 run_qa=True，返回 QA 检查报告")


class ValidatePlanRequest(BaseModel):
    """校验计划请求。"""

    plan: Dict[str, Any] = Field(..., description="待校验的进度计划 JSON")


class ValidatePlanResponse(BaseModel):
    """校验计划响应。"""

    valid: bool = Field(..., description="是否通过校验")
    message: str = Field("", description="校验说明")


class QARequest(BaseModel):
    """QA Agent 检查请求。"""

    plan: Dict[str, Any] = Field(..., description="待检查的进度计划 JSON")
    query: Optional[str] = Field(None, description="用户的原始需求，可选")
    conversation_id: Optional[str] = Field(None, description="Dify 会话 ID，续问时传入")


class QACheckItem(BaseModel):
    """QA 单项检查结果。"""

    item: str = Field(..., description="检查项名称")
    passed: bool = Field(..., description="是否通过")
    score: int = Field(0, ge=0, le=100, description="该项得分")
    reason: str = Field("", description="通过/不通过的原因")
    suggestion: str = Field("", description="修改建议")


class QAResponse(BaseModel):
    """QA Agent 检查响应。"""

    overall_score: int = Field(0, ge=0, le=100, description="综合得分")
    summary: str = Field("", description="总体评价")
    items: List[QACheckItem] = Field(default_factory=list, description="检查项列表")
    modification_report: str = Field("", description="修改报告 Markdown")
    raw: Optional[Dict[str, Any]] = Field(None, description="QA Agent 原始输出（调试用）")


class HistoryItem(BaseModel):
    """历史文件条目。"""

    file_name: str
    file_path: str
    project_name: str
    upload_time: str


class DeleteHistoryRequest(BaseModel):
    """删除历史文件请求。"""

    file_path: str


class PlanVisualizationData(BaseModel):
    """供前端渲染甘特图、资源曲线的数据包。"""

    overview: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    sections: Dict[str, str]
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    resource_plan: Dict[str, Any] = Field(default_factory=dict)
    risks: List[Dict[str, Any]] = Field(default_factory=list)
