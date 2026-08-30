"""本机历史文件接口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

from backend.config import HISTORY_DIR
from backend.core.models import DeleteHistoryRequest, HistoryItem

# 复用 legacy 历史模块
from backend.core.legacy.history import (
    delete_history_file,
    get_history_json_files,
    save_file_unique,
)

router = APIRouter(prefix="/history", tags=["History / 历史文件"])


@router.get("/list", response_model=List[HistoryItem], summary="列出历史文件")
def list_history():
    """返回本机历史工作区的 JSON 文件列表。"""
    return get_history_json_files()


@router.get("/load/{file_name}", summary="加载指定历史文件")
def load_history(file_name: str):
    """根据文件名加载历史计划 JSON。"""
    path = HISTORY_DIR / (file_name if file_name.endswith(".json") else f"{file_name}.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在：{file_name}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"file_name": file_name, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取文件失败：{exc}")


@router.post("/save", summary="保存计划到历史")
def save_history(file_name: str, plan: dict):
    """保存计划 JSON 到本机历史工作区。同名文件视为同一文件，不重复保存。"""
    content = json.dumps(plan, ensure_ascii=False, indent=2).encode("utf-8")
    ok, message = save_file_unique(file_name, content)
    if not ok:
        raise HTTPException(status_code=409, detail=message)
    return {"success": True, "path": message}


@router.post("/delete", summary="删除历史文件")
def delete_history(request: DeleteHistoryRequest):
    """删除指定的历史文件。"""
    # 安全检查：只允许删除历史目录内的文件
    target = Path(request.file_path).resolve()
    if not str(target).startswith(str(HISTORY_DIR.resolve())):
        raise HTTPException(status_code=400, detail="只能删除历史目录内的文件")
    ok = delete_history_file(str(target))
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"success": True}


def _save_plan_history(plan: dict, query: str = "") -> dict:
    """保存计划到历史文件（供 chat 接口调用）。"""
    import os
    import json
    from datetime import datetime
    
    history_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history")
    os.makedirs(history_dir, exist_ok=True)
    
    overview = plan.get("overview", {})
    project_name = overview.get("project_name", "未命名项目")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{project_name}_{timestamp}.json"
    file_path = os.path.join(history_dir, file_name)
    
    record = {
        "file_name": file_name,
        "project_name": project_name,
        "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "plan": plan,
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    
    return record
