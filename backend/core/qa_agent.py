"""QA Agent：对生成的进度计划进行质量检查并生成修改报告。

支持两种模式：
1. Dify QA Agent：配置 DIFY_QA_API_KEY + DIFY_QA_URL 后自动调用。
2. 本地规则 QA：未配置 Dify QA 时，使用内置规则快速检查。

输出统一为 QAResponse 模型。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from backend.config import (
    DIFY_QA_API_KEY,
    DIFY_QA_TYPE,
    DIFY_QA_URL,
)
from backend.core.models import QACheckItem, QAResponse


_QA_SYSTEM_PROMPT = """你是一名施工进度计划质量保证（QA）专家。请对下方 JSON 格式的施工进度计划进行逐项检查，并输出修改报告。

检查维度：
1. 数据完整性：必须包含 overview（project_name / total_duration_days / planned_start_date / planned_end_date）和 all_tasks_schedule（非空列表）。
2. 任务字段完整性：每个任务必须包含 task_id、task_name、start_date、finish_date、duration_days、assigned_resources。
3. 日期逻辑正确性：每个任务的 start_date <= finish_date；project 总工期与首尾日期一致。
4. 工期一致性：duration_days 应等于 (finish_date - start_date + 1)。
5. 关键路径一致性：critical_path_tasks 中的任务必须在 all_tasks_schedule 中存在。
6. 资源合理性：assigned_resources 应为字典，资源数量为正整数或小数。
7. 里程碑一致性：key_milestones 的日期应落在对应任务区间内。
8. 施工顺序合理性：分部编号应由小到大，关键路径任务应覆盖主要分部。

输出必须是 JSON，格式如下（不要包含 Markdown 代码块，直接输出 JSON）：
{
  "overall_score": 85,
  "summary": "计划整体合理，但存在...",
  "items": [
    {"item": "数据完整性", "passed": true, "score": 100, "reason": "字段齐全", "suggestion": ""},
    {"item": "日期逻辑", "passed": false, "score": 60, "reason": "任务 3.1.1 的 start_date 晚于 finish_date", "suggestion": "请调整 3.1.1 的日期使其 start <= finish"}
  ],
  "modification_report": "## 修改报告\\n\\n### 问题 1...\\n### 修改建议..."
}
"""


def check_plan(plan: Dict[str, Any], query: Optional[str] = None) -> QAResponse:
    """入口函数：优先调用 Dify QA Agent，未配置则回退本地规则 QA。"""
    if DIFY_QA_URL and DIFY_QA_API_KEY:
        try:
            return _call_dify_qa(plan, query)
        except Exception as exc:
            # Dify 调用失败时降级到本地 QA，并附带错误信息
            local = _local_qa_check(plan)
            local.summary = f"Dify QA 调用失败（{exc}），已降级为本地规则检查。\n{local.summary}"
            return local
    return _local_qa_check(plan)


def _call_dify_qa(plan: Dict[str, Any], query: Optional[str] = None) -> QAResponse:
    """调用 Dify QA Agent（Workflow / Chatflow / Agent）。"""
    headers = {
        "Authorization": f"Bearer {DIFY_QA_API_KEY}",
        "Content-Type": "application/json",
    }

    user_content = f"用户需求：{query or '自动生成施工进度计划'}\n\n进度计划 JSON：\n{json.dumps(plan, ensure_ascii=False, indent=2)}"

    if DIFY_QA_TYPE in ("chatflow", "agent"):
        payload: Dict[str, Any] = {
            "inputs": {},
            "query": _QA_SYSTEM_PROMPT + "\n\n" + user_content,
            "response_mode": "blocking",
            "user": "fastapi_qa",
        }
    else:
        # workflow 模式
        payload = {
            "inputs": {
                "plan": json.dumps(plan, ensure_ascii=False),
                "query": query or "",
                "system_prompt": _QA_SYSTEM_PROMPT,
            },
            "response_mode": "blocking",
            "user": "fastapi_qa",
        }

    resp = requests.post(DIFY_QA_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    # 解析 Dify 返回
    raw_answer = ""
    if isinstance(result, dict):
        raw_answer = result.get("answer") or result.get("data", {}).get("outputs", {}).get("text", "")
        if not raw_answer:
            outputs = result.get("data", {}).get("outputs") or result.get("outputs") or {}
            for key in ("qa_result", "result", "output", "structured_output"):
                if key in outputs:
                    raw_answer = outputs[key]
                    break

    qa_data = _parse_qa_json(raw_answer)
    return _build_qa_response(qa_data, raw=result)


def _parse_qa_json(raw: Any) -> Dict[str, Any]:
    """从字符串或字典中解析 QA JSON。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    text = raw.strip()
    if not text:
        return {}
    # 尝试去掉 markdown 代码块
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except Exception:
        return {}


def _build_qa_response(data: Dict[str, Any], raw: Optional[Dict[str, Any]] = None) -> QAResponse:
    """把解析后的 QA 数据映射到 QAResponse。"""
    items = []
    for it in data.get("items", []):
        items.append(
            QACheckItem(
                item=str(it.get("item", "")),
                passed=bool(it.get("passed", False)),
                score=int(it.get("score", 0)),
                reason=str(it.get("reason", "")),
                suggestion=str(it.get("suggestion", "")),
            )
        )
    return QAResponse(
        overall_score=int(data.get("overall_score", 0)),
        summary=str(data.get("summary", "")),
        items=items,
        modification_report=str(data.get("modification_report", "")),
        raw=raw,
    )


def _local_qa_check(plan: Dict[str, Any]) -> QAResponse:
    """本地规则 QA：不依赖外部模型，快速检查常见数据问题。"""
    items: List[QACheckItem] = []

    # 1. 数据完整性
    structured = plan.get("structured_output") if isinstance(plan.get("structured_output"), dict) else plan
    overview = structured.get("overview") if isinstance(structured, dict) else None
    tasks = structured.get("all_tasks_schedule") if isinstance(structured, dict) else None

    required_overview = ("project_name", "total_duration_days", "planned_start_date", "planned_end_date")
    missing_overview = [f for f in required_overview if not isinstance(overview, dict) or f not in overview]

    if missing_overview:
        items.append(
            QACheckItem(
                item="数据完整性",
                passed=False,
                score=40,
                reason=f"overview 缺少字段：{', '.join(missing_overview)}",
                suggestion="请补充 overview 中的必填字段。",
            )
        )
    else:
        items.append(
            QACheckItem(
                item="数据完整性",
                passed=True,
                score=100,
                reason="overview 与 all_tasks_schedule 结构完整",
                suggestion="",
            )
        )

    # 2. 任务字段完整性
    required_task = ("task_id", "task_name", "start_date", "finish_date", "duration_days")
    if not isinstance(tasks, list) or not tasks:
        items.append(
            QACheckItem(
                item="任务字段完整性",
                passed=False,
                score=0,
                reason="all_tasks_schedule 为空或不是列表",
                suggestion="请确保至少包含一道工序。",
            )
        )
    else:
        bad_tasks = []
        for idx, t in enumerate(tasks, 1):
            if not isinstance(t, dict):
                bad_tasks.append(f"第 {idx} 个任务不是对象")
                continue
            missing = [f for f in required_task if f not in t]
            if missing:
                bad_tasks.append(f"第 {idx} 个任务缺少 {', '.join(missing)}")
        if bad_tasks:
            items.append(
                QACheckItem(
                    item="任务字段完整性",
                    passed=False,
                    score=60,
                    reason="；".join(bad_tasks[:3]),
                    suggestion="请补充每个任务的必填字段。",
                )
            )
        else:
            items.append(
                QACheckItem(
                    item="任务字段完整性",
                    passed=True,
                    score=100,
                    reason=f"全部 {len(tasks)} 个任务字段完整",
                    suggestion="",
                )
            )

    # 3. 日期逻辑 / 工期一致性
    date_errors = []
    duration_errors = []
    if isinstance(tasks, list):
        for t in tasks:
            if not isinstance(t, dict):
                continue
            try:
                start = datetime.strptime(str(t["start_date"]), "%Y-%m-%d")
                finish = datetime.strptime(str(t["finish_date"]), "%Y-%m-%d")
                if start > finish:
                    date_errors.append(f"{t.get('task_id', '?')}: start_date > finish_date")
                expected = (finish - start).days + 1
                actual = int(t.get("duration_days", expected))
                if actual != expected:
                    duration_errors.append(
                        f"{t.get('task_id', '?')}: duration_days={actual}，但与日期差 {expected} 不符"
                    )
            except Exception as exc:
                date_errors.append(f"{t.get('task_id', '?')}: 日期解析失败 ({exc})")

    if date_errors:
        items.append(
            QACheckItem(
                item="日期逻辑正确性",
                passed=False,
                score=50,
                reason="；".join(date_errors[:3]),
                suggestion="请调整任务日期，确保开始日期不晚于结束日期。",
            )
        )
    else:
        items.append(
            QACheckItem(
                item="日期逻辑正确性",
                passed=True,
                score=100,
                reason="所有任务 start_date <= finish_date",
                suggestion="",
            )
        )

    if duration_errors:
        items.append(
            QACheckItem(
                item="工期一致性",
                passed=False,
                score=50,
                reason="；".join(duration_errors[:3]),
                suggestion="请核对 duration_days 与 (finish_date - start_date + 1) 是否一致。",
            )
        )
    else:
        items.append(
            QACheckItem(
                item="工期一致性",
                passed=True,
                score=100,
                reason="duration_days 与日期差一致",
                suggestion="",
            )
        )

    # 4. 关键路径一致性
    critical = structured.get("critical_path_tasks") if isinstance(structured, dict) else None
    if isinstance(critical, list) and tasks:
        task_ids = {str(t.get("task_id", "")) for t in tasks if isinstance(t, dict)}
        missing_critical = [c.get("task_id") for c in critical if isinstance(c, dict) and str(c.get("task_id", "")) not in task_ids]
        if missing_critical:
            items.append(
                QACheckItem(
                    item="关键路径一致性",
                    passed=False,
                    score=50,
                    reason=f"关键路径中的任务不在 all_tasks_schedule 中：{missing_critical[:3]}",
                    suggestion="请确保 critical_path_tasks 中的任务 ID 在任务列表中存在。",
                )
            )
        else:
            items.append(
                QACheckItem(
                    item="关键路径一致性",
                    passed=True,
                    score=100,
                    reason="关键路径任务均存在于任务列表",
                    suggestion="",
                )
            )
    else:
        items.append(
            QACheckItem(
                item="关键路径一致性",
                passed=True,
                score=100,
                reason="未提供关键路径或任务为空，跳过检查",
                suggestion="",
            )
        )

    # 5. 资源合理性
    resource_errors = []
    if isinstance(tasks, list):
        for t in tasks:
            if not isinstance(t, dict):
                continue
            res = t.get("assigned_resources")
            if res is None:
                continue
            if not isinstance(res, dict):
                resource_errors.append(f"{t.get('task_id', '?')}: assigned_resources 不是字典")
            else:
                for k, v in res.items():
                    if not isinstance(v, (int, float)) or v < 0:
                        resource_errors.append(f"{t.get('task_id', '?')}: 资源 {k} 数量异常 {v}")
                        break
    if resource_errors:
        items.append(
            QACheckItem(
                item="资源合理性",
                passed=False,
                score=60,
                reason="；".join(resource_errors[:3]),
                suggestion="请确保 assigned_resources 为 {资源名: 数量} 格式，数量为非负数。",
            )
        )
    else:
        items.append(
            QACheckItem(
                item="资源合理性",
                passed=True,
                score=100,
                reason="资源配置格式正确",
                suggestion="",
            )
        )

    # 计算综合得分
    if items:
        overall = round(sum(it.score for it in items) / len(items))
    else:
        overall = 0

    passed_items = [it.item for it in items if it.passed]
    failed_items = [it.item for it in items if not it.passed]
    summary = f"本地规则检查完成：通过 {len(passed_items)} 项，未通过 {len(failed_items)} 项。"
    if failed_items:
        summary += f" 待改进项：{', '.join(failed_items)}。"

    report_lines = ["## 修改报告（本地规则 QA）", "", summary, ""]
    for it in items:
        status = "✅ 通过" if it.passed else "❌ 未通过"
        report_lines.append(f"### {it.item} — {status}（{it.score} 分）")
        report_lines.append(f"- **原因**：{it.reason}")
        if it.suggestion:
            report_lines.append(f"- **建议**：{it.suggestion}")
        report_lines.append("")

    return QAResponse(
        overall_score=overall,
        summary=summary,
        items=items,
        modification_report="\n".join(report_lines),
    )
