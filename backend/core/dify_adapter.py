"""Dify 客户端适配器：把同步的 core.dify_client 包装成适合 FastAPI 的异步接口。

说明：
- 复用项目根目录 ``core/dify_client.py`` 的现有能力（重试、解析、清洗）。
- 提供同步 ``chat`` 和异步流式 ``stream_chat`` 两种调用方式。
- 流式接口把 Dify 的进度事件、文字增量、最终 plan 统一成 Server-Sent Events。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import anyio

# 复用 legacy 核心模块（已从根目录 core/ 迁移至此）
from backend.core.legacy.data import normalize_to_wrapped, validate_data_structure
from backend.core.legacy.dify_client import call_dify_chatflow

from backend.config import (
    DIFY_CHATFLOW_URL,
    DIFY_MAX_RETRIES,
    DIFY_RETRY_INTERVAL,
    DIFY_TIMEOUT,
)
from backend.core.models import ChatResponse


class DifyEvent:
    """流式事件统一封装。"""

    def __init__(self, event: str, data: Dict[str, Any]):
        self.event = event
        self.data = data

    def to_sse(self) -> str:
        """转成 SSE 格式字符串。"""
        payload = json.dumps(self.data, ensure_ascii=False)
        return f"event: {self.event}\ndata: {payload}\n\n"


async def stream_chat(
    query: str,
    *,
    files: Optional[List[Any]] = None,
    conversation_id: Optional[str] = None,
    current_plan_json: Optional[Dict[str, Any]] = None,
    user_id: str = "fastapi_web",
) -> AsyncGenerator[DifyEvent, None]:
    """流式调用 Dify Chatflow，输出 SSE 事件。

    事件类型：
    - progress:  {"message": "..."}  工作流节点进度
    - answer:    {"delta": "..."}    文字增量（已清洗，不含 JSON）
    - plan:      {"plan": {...}}     最终解析出的进度计划 JSON
    - error:     {"message": "..."}  错误信息
    - done:      {}                   流结束
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[DifyEvent] = asyncio.Queue()

    def on_progress(message: str) -> None:
        asyncio.run_coroutine_threadsafe(
            queue.put(DifyEvent("progress", {"message": message})),
            loop,
        )

    async def _producer() -> None:
        try:
            # 在线程池中执行同步的 Dify 调用，避免阻塞事件循环
            answer_text, structured_output, new_conv_id = await anyio.to_thread.run_sync(
                lambda: call_dify_chatflow(
                    query,
                    files=files,
                    conversation_id=conversation_id,
                    current_plan_json=current_plan_json,
                    on_progress=on_progress,
                ),
                limiter=None,
            )

            # 推送文字（一次性推送完整文字；如需逐字效果，可在此拆分）
            if answer_text:
                await queue.put(DifyEvent("answer", {"delta": answer_text}))

            # 推送 plan（优先用 structured_output，其次用 answer_text 解析）
            plan = None
            if structured_output:
                plan = _normalize_plan(structured_output)
            if not plan and answer_text:
                plan = _normalize_plan(answer_text)
            if plan:
                await queue.put(DifyEvent("plan", {"plan": plan}))

            await queue.put(
                DifyEvent("done", {"conversation_id": new_conv_id})
            )
        except Exception as exc:
            await queue.put(DifyEvent("error", {"message": str(exc)}))
            await queue.put(DifyEvent("done", {}))

    producer_task = asyncio.create_task(_producer())

    try:
        while True:
            # 使用 timeout 以便能检测 producer 结束
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if producer_task.done() and queue.empty():
                    break
                continue
            yield event
            if event.event == "done":
                break
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass


async def chat(
    query: str,
    *,
    files: Optional[List[Any]] = None,
    conversation_id: Optional[str] = None,
    current_plan_json: Optional[Dict[str, Any]] = None,
    user_id: str = "fastapi_web",
) -> ChatResponse:
    """非流式调用 Dify Chatflow，返回完整响应。"""

    def _call() -> tuple:
        return call_dify_chatflow(
            query,
            files=files,
            conversation_id=conversation_id,
            current_plan_json=current_plan_json,
        )

    answer_text, structured_output, new_conv_id = await anyio.to_thread.run_sync(
        _call, limiter=None
    )

    plan = _normalize_plan(structured_output)
    return ChatResponse(
        answer=answer_text or "",
        plan=plan or {},
        conversation_id=new_conv_id,
    )


def _parse_text_plan_to_json(text: str) -> Optional[Dict[str, Any]]:
    """将 Dify 输出的格式化文本（施工进度计划说明书）解析为结构化 JSON。
    
    支持格式：
    - 项目概览（项目名称、总工期、计划开工/竣工日期）
    - 施工分部进度详解（工序编号、工序名称、开始日期、完成日期、工期、资源配置）
    """
    import re
    
    if not text or not isinstance(text, str):
        return None
    
    # 提取项目概览
    overview = {}
    
    # 项目名称
    name_match = re.search(r'项目名称[：:]\s*(.+)', text)
    if name_match:
        overview['project_name'] = name_match.group(1).strip()
    
    # 总工期
    duration_match = re.search(r'总工期[：:]\s*(\d+)\s*天', text)
    if duration_match:
        overview['total_duration_days'] = int(duration_match.group(1))
    
    def _normalize_date(s: str) -> str:
        """将 2026-4-1 / 2026年4月1日 等格式统一为 2026-04-01"""
        s = s.replace('年', '-').replace('月', '-').replace('日', '')
        parts = s.split('-')
        if len(parts) == 3:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        return s

    # 计划开工日期
    start_match = re.search(r'计划开工日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', text)
    if start_match:
        overview['planned_start_date'] = _normalize_date(start_match.group(1))

    # 计划竣工日期
    end_match = re.search(r'计划竣工日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', text)
    if end_match:
        overview['planned_end_date'] = _normalize_date(end_match.group(1))
    
    if not overview:
        return None
    
    # 提取工序列表（兼容多种格式）
    tasks = []
    
    # 格式1: "*   工序 1.1：名称\n    *   开始日期：...，完成日期：...，工期：...\n    *   主要资源配置：..."
    # 格式2: "* 工序编号：1.1\n  * 工序名称：xxx\n  * 开始日期：..."
    # 格式3: "工序编号：1.1\n工序名称：xxx\n开始日期：..."
    
    # 先尝试格式1（Dify 实际输出）
    task_blocks = re.split(r'\n\s*\*\s*工序\s+([\d.]+)[：:]', text)
    if len(task_blocks) > 1:
        # task_blocks[0] 是前面的内容，之后每两块是一对：(task_id, task_content)
        for i in range(1, len(task_blocks), 2):
            task_id = task_blocks[i].strip()
            block = task_blocks[i+1] if i+1 < len(task_blocks) else ''
            
            task = {'task_id': task_id}
            
            # 提取工序名称（冒号后面到换行）
            name_m = re.match(r'\s*(.+?)(?:\n|$)', block)
            if name_m:
                task['task_name'] = name_m.group(1).strip()
            
            # 提取日期（在同一行："开始日期：2026-04-01，完成日期：2026-04-10，工期：10天"）
            date_line = re.search(r'开始日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)[，,]\s*完成日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)[，,]\s*工期[：:]\s*(\d+)\s*天', block)
            if date_line:
                task['start_date'] = _normalize_date(date_line.group(1))
                task['finish_date'] = _normalize_date(date_line.group(2))
                task['duration_days'] = int(date_line.group(3))
            else:
                # 尝试分开匹配
                start_m = re.search(r'开始日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', block)
                if start_m:
                    task['start_date'] = _normalize_date(start_m.group(1))
                finish_m = re.search(r'完成日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', block)
                if finish_m:
                    task['finish_date'] = _normalize_date(finish_m.group(1))
                dur_m = re.search(r'工期[：:]\s*(\d+)\s*天', block)
                if dur_m:
                    task['duration_days'] = int(dur_m.group(1))
            
            # 提取资源配置
            res_m = re.search(r'主要资源配置[：:]\s*(.+)', block)
            if res_m:
                res_text = res_m.group(1).strip()
                resources = {}
                for part in re.split(r'[,，]', res_text):
                    part = part.strip()
                    m = re.search(r'(\S+?)\s*(\d+)\s*人', part)
                    if m:
                        resources[m.group(1)] = int(m.group(2))
                task['assigned_resources'] = resources
            
            if 'task_name' in task:
                tasks.append(task)
    
    # 如果格式1没匹配到，尝试格式2/3
    if not tasks:
        task_pattern = r'(?:\*\s*)?工序编号[：:]\s*([\d.]+)\s*\n(.*?)(?=(?:\*\s*)?工序编号[：:]|\n【|\n三、|\n四、|\Z)'
        task_matches = re.finditer(task_pattern, text, re.DOTALL)
        
        for match in task_matches:
            task_id = match.group(1).strip()
            task_block = match.group(2)
            
            task = {'task_id': task_id}
            
            name_m = re.search(r'工序名称[：:]\s*(.+)', task_block)
            if name_m:
                task['task_name'] = re.sub(r'^\*\s*', '', name_m.group(1)).strip()
            
            start_m = re.search(r'开始日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', task_block)
            if start_m:
                task['start_date'] = _normalize_date(start_m.group(1))
            
            finish_m = re.search(r'完成日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', task_block)
            if finish_m:
                task['finish_date'] = _normalize_date(finish_m.group(1))
            
            dur_m = re.search(r'工期[：:]\s*(\d+)\s*天', task_block)
            if dur_m:
                task['duration_days'] = int(dur_m.group(1))
            
            res_m = re.search(r'主要资源配置[：:]\s*(.+)', task_block)
            if res_m:
                res_text = res_m.group(1).strip()
                resources = {}
                for part in re.split(r'[,，]', res_text):
                    part = part.strip()
                    m = re.search(r'(\S+?)\s*(\d+)\s*人', part)
                    if m:
                        resources[m.group(1)] = int(m.group(2))
                task['assigned_resources'] = resources
            
            if 'task_name' in task:
                tasks.append(task)
    
    if not tasks:
        return None
    
    # 提取关键路径（Dify 输出格式："1. 1.1 现场临建..."）
    critical_path = []
    cp_match = re.search(r'三、\s*关键路径\s*\n(.*?)(?=四、|\Z)', text, re.DOTALL)
    if cp_match:
        cp_text = cp_match.group(1)
        for line in cp_text.split('\n'):
            # 匹配 "1. 1.1 现场临建..." 或 "1.1 现场临建..."
            # 只提取以数字.数字开头的工序编号，排除纯数字序号
            m = re.search(r'(?:\d+\.\s+)?(\d+\.\d+)\s+', line)
            if m:
                critical_path.append(m.group(1))

    # 提取关键里程碑
    milestones = []
    ms_match = re.search(r'四、\s*关键里程碑\s*\n(.*?)(?=五、|\Z)', text, re.DOTALL)
    if ms_match:
        ms_text = ms_match.group(1)
        # 按顶层 "*   " 分割里程碑（不匹配缩进的子项 "    *   "）
        ms_items = re.split(r'\n\*\s{1,3}(?!\s)', ms_text)
        for item in ms_items:
            item = item.strip()
            if not item:
                continue
            # 里程碑名称在第一行
            name_m = re.search(r'^[\*＊\s]*(.+?)(?:\n|$)', item)
            date_m = re.search(r'日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)', item)
            desc_m = re.search(r'(?:说明|描述)[：:]\s*(.+)', item)
            if name_m and date_m:
                milestones.append({
                    'name': name_m.group(1).strip().lstrip('* ').strip(),
                    'date': _normalize_date(date_m.group(1)),
                    'description': desc_m.group(1).strip() if desc_m else ''
                })

    # 提取资源计划
    resource_plan = {}
    rp_match = re.search(r'五、\s*资源计划\s*\n(.*?)(?=六、|\Z)', text, re.DOTALL)
    if rp_match:
        rp_text = rp_match.group(1)
        peak_m = re.search(r'人力峰值[：:]\s*(\d+)\s*人', rp_text)
        if peak_m:
            resource_plan['peak_manpower'] = int(peak_m.group(1))
        equipment = {}
        # 匹配 "*   塔吊：1台" 或 "塔吊：1台" 等格式
        for eq_m in re.finditer(r'[\*＊\s]*([^*＊\n：:]+?)[：:]\s*(\d+)\s*(台|辆|套|部)', rp_text):
            name = eq_m.group(1).strip().lstrip('* ').strip()
            if name and len(name) < 20:  # 过滤过长的误匹配
                equipment[name] = int(eq_m.group(2))
        if equipment:
            resource_plan['equipment_peak'] = equipment

    # 提取风险
    risks = []
    risk_match = re.search(r'六、\s*风险与应对\s*\n(.*?)$', text, re.DOTALL)
    if risk_match:
        risk_text = risk_match.group(1)
        risk_names = re.findall(r'风险名称[：:]\s*(.+)', risk_text)
        risk_measures = re.findall(r'应对措施[：:]\s*(.+)', risk_text)
        for i in range(min(len(risk_names), len(risk_measures))):
            risks.append({
                'risk_name': risk_names[i].strip(),
                'mitigation': risk_measures[i].strip()
            })

    # 生成人员配置数据（从工序资源中汇总）
    personnel_dates = []
    personnel_series = {}
    for t in tasks:
        start = t.get('start_date', '')
        if start and start not in personnel_dates:
            personnel_dates.append(start)
    personnel_dates.sort()

    for t in tasks:
        res = t.get('assigned_resources', {})
        for name, count in res.items():
            if name not in personnel_series:
                personnel_series[name] = [0] * len(personnel_dates)
            start = t.get('start_date', '')
            if start in personnel_dates:
                idx = personnel_dates.index(start)
                personnel_series[name][idx] += count

    personnel_data = {'dates': personnel_dates, 'series': personnel_series} if personnel_dates else {}

    # 生成设备数据
    equipment_categories = []
    equipment_values = []
    eq_from_resource = resource_plan.get('equipment_peak', {})
    if eq_from_resource:
        for name, count in eq_from_resource.items():
            equipment_categories.append(name)
            equipment_values.append(count)
    else:
        # 从工序资源中提取设备（包含人名的排除，剩下的当做设备）
        eq_keywords = ('机', '吊', '泵', '车', '电梯', '篮', '钻', '炮', '焊', '切割', '整平')
        eq_skip = ('工人', '人员', '管理', '技术', '安全', '质量', '资料', '测量')
        eq_counts = {}
        for t in tasks:
            for name, count in t.get('assigned_resources', {}).items():
                # 排除纯人工工种
                if any(skip in name for skip in eq_skip):
                    continue
                if any(kw in name for kw in eq_keywords):
                    eq_counts[name] = max(eq_counts.get(name, 0), count)
        for name, count in eq_counts.items():
            equipment_categories.append(name)
            equipment_values.append(count)

    equipment_data = {'categories': equipment_categories, 'values': equipment_values} if equipment_categories else {}

    # 构建完整的计划 JSON
    plan = {
        'overview': overview,
        'all_tasks_schedule': tasks,
        'critical_path_tasks': critical_path,
        'key_milestones': milestones,
        'resource_plan': resource_plan,
        'risks': risks,
        'personnel_data': personnel_data,
        'equipment_data': equipment_data
    }
    
    return plan


def _normalize_plan(raw: Any) -> Optional[Dict[str, Any]]:
    """把 Dify 返回的结构化输出统一解包成扁平 plan。"""
    if not raw:
        return None
    if isinstance(raw, dict):
        # 外层包装：structured_output / plan / output ...
        if "structured_output" in raw and isinstance(raw["structured_output"], dict):
            inner = raw["structured_output"]
        elif "overview" in raw and "all_tasks_schedule" in raw:
            inner = raw
        else:
            # 再扫一层常见 key
            inner = None
            for key in ("plan", "output", "result", "adjusted_plan", "optimized_plan"):
                if key in raw and isinstance(raw[key], dict):
                    inner = raw[key]
                    break
            if inner is None:
                return None
        valid, _ = validate_data_structure(inner)
        return inner if valid else None
    if isinstance(raw, str):
        try:
            return _normalize_plan(json.loads(raw))
        except Exception:
            # JSON 解析失败，尝试作为格式化文本解析
            text_plan = _parse_text_plan_to_json(raw)
            if text_plan:
                return text_plan
            return None
    return None


def build_user_query(
    query: str,
    *,
    file_contents: Optional[List[Dict[str, str]]] = None,
    current_plan_json: Optional[Dict[str, Any]] = None,
) -> str:
    """和前端约定：后端负责把上传文件内容拼进 query。"""
    final_query = query
    if file_contents:
        for fc in file_contents:
            name = fc.get("name", "上传文件")
            content = fc.get("content", "")
            final_query += f"\n\n===== 文件 {name} 内容 =====\n{content}\n"
    if current_plan_json:
        plan_str = json.dumps(current_plan_json, ensure_ascii=False, indent=2)
        final_query = (
            f"【用户要求】\n{final_query}\n\n"
            f"【当前已有进度计划数据】\n{plan_str}\n\n"
            f"请基于当前进度计划数据，结合用户要求进行生成/调整。"
        )
    return final_query
