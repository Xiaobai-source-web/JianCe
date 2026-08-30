"""FastAPI 后端接口测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


SAMPLE_PLAN = {
    "overview": {
        "project_name": "测试项目",
        "total_duration_days": 5,
        "planned_start_date": "2026-03-01",
        "planned_end_date": "2026-03-05",
    },
    "all_tasks_schedule": [
        {
            "task_id": "1.1.1",
            "task_name": "施工准备",
            "start_date": "2026-03-01",
            "finish_date": "2026-03-05",
            "duration_days": 5,
            "assigned_resources": {"管理人员": 3},
        }
    ],
}


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_validate_plan_ok():
    with TestClient(app) as client:
        resp = client.post("/api/v1/plan/validate", json={"plan": SAMPLE_PLAN})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


def test_validate_plan_missing_field():
    plan = {"overview": {"project_name": "测试项目"}}
    with TestClient(app) as client:
        resp = client.post("/api/v1/plan/validate", json={"plan": plan})
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


def test_qa_check_local():
    with TestClient(app) as client:
        resp = client.post("/api/v1/plan/qa", json={"plan": SAMPLE_PLAN})
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_score" in data
        assert "items" in data
        assert "modification_report" in data
        assert data["overall_score"] == 100


def test_qa_check_detects_bad_date():
    plan = {
        "overview": {
            "project_name": "测试项目",
            "total_duration_days": 5,
            "planned_start_date": "2026-03-01",
            "planned_end_date": "2026-03-05",
        },
        "all_tasks_schedule": [
            {
                "task_id": "1.1.1",
                "task_name": "施工准备",
                "start_date": "2026-03-06",
                "finish_date": "2026-03-01",
                "duration_days": 5,
            }
        ],
    }
    with TestClient(app) as client:
        resp = client.post("/api/v1/plan/qa", json={"plan": plan})
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] < 100
        failed_items = [it["item"] for it in data["items"] if not it["passed"]]
        assert "日期逻辑正确性" in failed_items


def test_visualization():
    with TestClient(app) as client:
        resp = client.post("/api/v1/plan/visualization", json=SAMPLE_PLAN)
        assert resp.status_code == 200
        data = resp.json()
        assert data["overview"]["project_name"] == "测试项目"
        assert len(data["tasks"]) == 1
        assert "1" in data["sections"]


def test_history_list():
    with TestClient(app) as client:
        resp = client.get("/api/v1/history/list")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_upload_text_file():
    from io import BytesIO

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/upload/files",
            files={"files": ("test.txt", BytesIO(b"hello world"), "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["files"]) == 1
        assert data["files"][0]["content"] == "hello world"


def test_text_plan_parser():
    """测试文本格式计划解析器"""
    from backend.core.dify_adapter import _parse_text_plan_to_json
    
    # 模拟 Dify 输出的格式化文本
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
  * 主要资源配置：桩机 2台，钢筋工 8人，混凝土工 6人"""
    
    result = _parse_text_plan_to_json(sample_text)
    
    assert result is not None, "应该能解析文本格式计划"
    assert "overview" in result, "应该包含 overview"
    assert result["overview"]["project_name"] == "某市高新区科技创新中心办公楼"
    assert result["overview"]["total_duration_days"] == 305
    assert result["overview"]["planned_start_date"] == "2026-04-01"
    assert result["overview"]["planned_end_date"] == "2027-01-31"
    assert len(result["all_tasks_schedule"]) == 3, "应该解析出3个工序"
    assert result["all_tasks_schedule"][0]["task_id"] == "1.1"
    assert result["all_tasks_schedule"][0]["task_name"] == "现场临建与围挡搭建"
    assert result["all_tasks_schedule"][0]["assigned_resources"]["普工"] == 10
    assert result["all_tasks_schedule"][0]["assigned_resources"]["木工"] == 5
