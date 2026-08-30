"""聊天 / 生成计划接口。"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from backend.core.dify_adapter import DifyEvent, chat as dify_chat, stream_chat
from backend.core.models import ChatRequest, ChatResponse
from backend.core.qa_agent import check_plan

router = APIRouter(prefix="/chat", tags=["Chat / 生成计划"])


@router.post("/generate", response_model=ChatResponse, summary="非流式生成进度计划")
async def generate_plan(request: ChatRequest):
    """接收用户请求，调用 Dify 主工作流生成进度计划。

    若 ``run_qa=True``，生成后会自动调用 QA Agent 检查并返回修改报告。
    """
    response = await dify_chat(
        request.query,
        conversation_id=request.conversation_id,
        current_plan_json=request.current_plan_json,
    )

    if request.run_qa and response.plan:
        response.qa_report = check_plan(response.plan, query=request.query).model_dump()

    return response


@router.get("/stream", summary="流式生成进度计划（SSE）")
async def stream_generate_plan(
    query: str,
    conversation_id: str = "",
    current_plan_json: str = "",
    run_qa: bool = True,
):
    """流式接口（GET，供 EventSource 使用），通过 Server-Sent Events 推送：

    - progress: 工作流节点进度
    - answer:   AI 文字说明增量
    - plan:     最终解析出的进度计划 JSON
    - qa_report:QA 检查报告（流结束时推送，默认开启）
    - error:    错误信息
    - done:     流结束
    """
    import json

    conv_id = conversation_id or None
    plan_json: Dict[str, Any] = {}
    if current_plan_json:
        try:
            plan_json = json.loads(current_plan_json)
        except Exception:
            plan_json = {}

    async def event_generator():
        final_plan: Dict[str, Any] = {}
        final_conv_id: str | None = None

        raw_answer_parts = []  # 收集原始文字

        async for event in stream_chat(
            query,
            conversation_id=conv_id,
            current_plan_json=plan_json or None,
        ):
            if event.event == "answer":
                raw_answer_parts.append(event.data.get("delta", ""))
            if event.event == "plan":
                final_plan = event.data.get("plan", {})
            if event.event == "done":
                final_conv_id = event.data.get("conversation_id")
            yield event.to_sse()

        # 保存 Dify 原始输出到文件（调试用）
        if raw_answer_parts:
            try:
                import os
                log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, "dify_raw_output.txt")
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("".join(raw_answer_parts))
            except Exception:
                pass

        # 自动保存生成的计划到历史文件
        if final_plan:
            try:
                from backend.api.history import _save_plan_history
                _save_plan_history(final_plan, query=query)
            except Exception:
                pass

        # 流结束后调用本地 QA（默认开启）
        if run_qa and final_plan:
            qa_result = check_plan(final_plan, query=query)
            yield DifyEvent("qa_report", qa_result.model_dump()).to_sse()

        # 最后再发一次 done，附带 conversation_id
        yield DifyEvent("done", {"conversation_id": final_conv_id}).to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream/mock", summary="模拟流式生成（测试用，不消耗 Token）")
async def mock_stream_generate_plan():
    """模拟 Dify 返回格式化文本计划，用于测试前端解析和渲染，不消耗 Token。"""
    sample_text = """施工进度计划说明书

一、项目概览

* 项目名称：某市高新区科技创新中心办公楼
* 总工期：305 天
* 计划开工日期：2026年4月1日
* 计划竣工日期：2027年1月31日

二、施工分部进度详解

本部分按施工分部（依据工序编号第一段数字分组）列出所有工序的详细安排。

【1. 前期准备阶段】

* 工序编号：1.1
  * 工序名称：现场临建与围挡搭建
  * 开始日期：2026-04-01
  * 完成日期：2026-04-10
  * 工期：10 天
  * 主要资源配置：普工 10人，木工 5人

* 工序编号：1.2
  * 工序名称：技术准备与图纸会审
  * 开始日期：2026-04-11
  * 完成日期：2026-04-20
  * 工期：10 天
  * 主要资源配置：技术员 3人，工程师 2人

【2. 基础工程阶段】

* 工序编号：2.1
  * 工序名称：旋挖灌注桩施工
  * 开始日期：2026-04-21
  * 完成日期：2026-05-15
  * 工期：25 天
  * 主要资源配置：桩机 2台，钢筋工 8人，混凝土工 6人

* 工序编号：2.2
  * 工序名称：承台及地梁施工
  * 开始日期：2026-05-16
  * 完成日期：2026-06-05
  * 工期：21 天
  * 主要资源配置：钢筋工 10人，木工 8人，混凝土工 5人

【3. 主体结构阶段】

* 工序编号：3.1
  * 工序名称：一层框架结构施工
  * 开始日期：2026-06-06
  * 完成日期：2026-06-25
  * 工期：20 天
  * 主要资源配置：钢筋工 12人，木工 10人，混凝土工 8人，塔吊 1台

* 工序编号：3.2
  * 工序名称：二层框架结构施工
  * 开始日期：2026-06-26
  * 完成日期：2026-07-15
  * 工期：20 天
  * 主要资源配置：钢筋工 12人，木工 10人，混凝土工 8人，塔吊 1台

* 工序编号：3.3
  * 工序名称：三至十二层框架结构施工
  * 开始日期：2026-07-16
  * 完成日期：2026-10-15
  * 工期：92 天
  * 主要资源配置：钢筋工 12人，木工 10人，混凝土工 8人，塔吊 1台

【4. 二次结构与装修阶段】

* 工序编号：4.1
  * 工序名称：砌体工程
  * 开始日期：2026-10-16
  * 完成日期：2026-11-15
  * 工期：31 天
  * 主要资源配置：瓦工 15人，普工 8人

* 工序编号：4.2
  * 工序名称：内外墙抹灰
  * 开始日期：2026-11-16
  * 完成日期：2026-12-05
  * 工期：20 天
  * 主要资源配置：抹灰工 12人，普工 6人

* 工序编号：4.3
  * 工序名称：门窗安装
  * 开始日期：2026-12-06
  * 完成日期：2026-12-20
  * 工期：15 天
  * 主要资源配置：安装工 8人

* 工序编号：4.4
  * 工序名称：地面工程
  * 开始日期：2026-12-21
  * 完成日期：2027-01-05
  * 工期：16 天
  * 主要资源配置：地面工 10人，普工 5人

【5. 机电安装阶段】

* 工序编号：5.1
  * 工序名称：给排水系统安装
  * 开始日期：2026-11-01
  * 完成日期：2026-12-15
  * 工期：45 天
  * 主要资源配置：水电工 8人

* 工序编号：5.2
  * 工序名称：电气系统安装
  * 开始日期：2026-11-01
  * 完成日期：2026-12-20
  * 工期：50 天
  * 主要资源配置：电工 10人

* 工序编号：5.3
  * 工序名称：消防系统安装
  * 开始日期：2026-12-01
  * 完成日期：2027-01-10
  * 工期：41 天
  * 主要资源配置：消防安装工 6人

* 工序编号：5.4
  * 工序名称：电梯安装
  * 开始日期：2026-10-20
  * 完成日期：2026-12-30
  * 工期：72 天
  * 主要资源配置：电梯安装工 4人

【6. 收尾与验收阶段】

* 工序编号：6.1
  * 工序名称：室外工程（道路、绿化）
  * 开始日期：2027-01-06
  * 完成日期：2027-01-20
  * 工期：15 天
  * 主要资源配置：市政工 8人，普工 6人

* 工序编号：6.2
  * 工序名称：竣工清理与资料整理
  * 开始日期：2027-01-21
  * 完成日期：2027-01-25
  * 工期：5 天
  * 主要资源配置：普工 8人，资料员 2人

* 工序编号：6.3
  * 工序名称：消防验收
  * 开始日期：2027-01-26
  * 完成日期：2027-01-28
  * 工期：3 天
  * 主要资源配置：技术人员 2人

* 工序编号：6.4
  * 工序名称：竣工验收与移交
  * 开始日期：2027-01-29
  * 完成日期：2027-01-31
  * 工期：3 天
  * 主要资源配置：项目经理 1人，技术人员 3人"""

    import asyncio
    from backend.core.dify_adapter import _parse_text_plan_to_json, DifyEvent

    async def event_generator():
        # 模拟进度消息
        yield DifyEvent("progress", {"message": "正在解析需求..."}).to_sse()
        await asyncio.sleep(0.3)
        yield DifyEvent("progress", {"message": "正在分解 WBS 工作包..."}).to_sse()
        await asyncio.sleep(0.3)
        yield DifyEvent("progress", {"message": "正在计算关键路径..."}).to_sse()
        await asyncio.sleep(0.3)
        yield DifyEvent("progress", {"message": "正在优化资源配置..."}).to_sse()
        await asyncio.sleep(0.3)

        # 推送文字
        yield DifyEvent("answer", {"delta": sample_text}).to_sse()

        # 解析并推送 plan
        plan = _parse_text_plan_to_json(sample_text)
        if plan:
            yield DifyEvent("plan", {"plan": plan}).to_sse()

        yield DifyEvent("done", {}).to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream/debug", summary="调试模式：显示 Dify 原始输出（测试用）")
async def debug_stream_generate_plan(
    query: str = "项目为三层框架办公楼，建筑面积3000平米",
):
    """调用 Dify 并将原始响应推送到前端，用于调试文本解析。"""
    import asyncio
    from backend.core.dify_adapter import DifyEvent, stream_chat

    async def event_generator():
        async for event in stream_chat(query):
            # 所有事件都原样推送，包括原始文本
            yield event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



