"""进度计划校验、可视化数据、QA 检查接口。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from backend.core.models import (
    PlanVisualizationData,
    QARequest,
    QAResponse,
    ValidatePlanRequest,
    ValidatePlanResponse,
)
from backend.core.qa_agent import check_plan

# 复用 legacy 数据处理模块
from backend.core.legacy.data import (
    calculate_daily_resources,
    get_critical_task_ids,
    get_section_mapping,
    normalize_to_wrapped,
    tasks_to_dataframe,
    validate_data_structure,
)

router = APIRouter(prefix="/plan", tags=["Plan / 计划处理"])


@router.post("/validate", response_model=ValidatePlanResponse, summary="校验计划数据结构")
def validate_plan(request: ValidatePlanRequest):
    """校验传入的进度计划 JSON 是否符合前端渲染要求。"""
    valid, message = validate_data_structure(request.plan)
    return ValidatePlanResponse(valid=valid, message=message)


@router.post("/visualization", response_model=PlanVisualizationData, summary="生成可视化数据包")
def build_visualization_data(plan: Dict[str, Any]):
    """把原始计划 JSON 转换为前端甘特图、资源曲线所需的结构化数据。"""
    wrapped = normalize_to_wrapped(plan)
    structured = wrapped.get("structured_output", {})

    valid, message = validate_data_structure(wrapped)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    overview = structured.get("overview", {})
    tasks = structured.get("all_tasks_schedule", [])
    critical_path = structured.get("critical_path_tasks", [])
    milestones = structured.get("key_milestones", [])
    resource_plan = structured.get("resource_plan", {})
    risks = structured.get("risks", [])

    critical_ids = get_critical_task_ids(critical_path)
    tasks_df = tasks_to_dataframe(tasks, critical_ids)
    sections = get_section_mapping(tasks)

    return PlanVisualizationData(
        overview=overview,
        tasks=tasks,
        sections=sections,
        milestones=milestones if isinstance(milestones, list) else [],
        resource_plan=resource_plan if isinstance(resource_plan, dict) else {},
        risks=risks if isinstance(risks, list) else [],
    )


@router.post("/qa", response_model=QAResponse, summary="调用 QA Agent 检查计划")
def qa_check(request: QARequest):
    """对进度计划进行 QA 检查，返回评分、检查项和修改报告。"""
    return check_plan(request.plan, query=request.query)


@router.post("/qa-report-md", summary="生成 Markdown 修改报告")
def qa_report_markdown(request: QARequest):
    """仅返回 QA 修改报告文本（Markdown）。"""
    result = check_plan(request.plan, query=request.query)
    return {"modification_report": result.modification_report}


@router.post("/daily-resources", summary="计算每日资源负荷")
def daily_resources(plan: Dict[str, Any]):
    """计算每日人力资源负荷，用于前端资源曲线。"""
    wrapped = normalize_to_wrapped(plan)
    structured = wrapped.get("structured_output", {})

    valid, message = validate_data_structure(wrapped)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    tasks = structured.get("all_tasks_schedule", [])
    critical_path = structured.get("critical_path_tasks", [])
    critical_ids = get_critical_task_ids(critical_path)
    tasks_df = tasks_to_dataframe(tasks, critical_ids)
    date_range, daily_manpower, details = calculate_daily_resources(tasks_df)

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in date_range],
        "daily_manpower": daily_manpower,
        "details": details,
    }
