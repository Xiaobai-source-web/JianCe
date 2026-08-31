# 📐 施工进度计划智能助手

> 基于 **FastAPI + Dify 多智能体 + 通义千问 + ECharts** 的施工进度计划智能生成与可视化系统。

## 🚀 在线体验

### 👉 [点击进入施工进度计划智能助手](https://static-site-1-eight.vercel.app/)

**当前线上架构：**

```text
Vercel 前端
     ↓ HTTPS / SSE
阿里云 FC · FastAPI
     ↓
Dify 多智能体 / 通义千问
```

后端 API：
`https://progresplan-api-jbmavylupd.cn-shenzhen.fcapp.run`

---

## 📖 项目简介

本项目面向施工进度计划编制场景。

用户可通过自然语言描述工程需求或上传项目资料，由 **Dify 多智能体工作流**完成任务分析与施工进度计划生成，FastAPI 后端负责工作流调度、QA 检查、文件解析及数据处理，并通过 Web 看板展示施工计划。

主要输出包括：

- 📊 施工甘特图与关键路径
- 👷 人员配置曲线
- 🚜 设备需求分析
- 📌 关键里程碑
- ⚠️ 施工风险与应对措施
- ✅ AI 生成结果 QA 检查
- 📈 多方案进度对比

---

## 🏗️ 系统架构

```text
                    用户
                     │
                     ▼
             ┌──────────────┐
             │    Vercel    │
             │ HTML/CSS/JS  │
             │   ECharts    │
             └──────┬───────┘
                    │ HTTPS / SSE
                    ▼
        ┌────────────────────────┐
        │ Alibaba Cloud FC       │
        │ FastAPI Backend        │
        │                        │
        │ /health                │
        │ /api/v1/chat/*         │
        │ /api/v1/upload/*       │
        │ /api/v1/plan/*         │
        └───────────┬────────────┘
                    │
             ┌──────┴──────┐
             ▼             ▼
           Dify          通义千问
        Multi-Agent        LLM
```

---

## 🔄 部署方案演进

### 初版：FastAPI 前后端一体

项目最初采用 FastAPI 同时托管前端静态页面和后端 API：

```text
Browser
   ↓
Alibaba FC
   ↓
FastAPI
 ├─ HTML / Static
 └─ API
```

该方案本地开发简单，但部署到阿里云 FC 后，默认测试域名对 HTML 页面直接展示存在限制。

### 当前：Vercel + FC 前后端分离

因此线上版本调整为：

```text
Browser
   ↓
Vercel              ← 前端
   ↓
Alibaba Cloud FC    ← FastAPI 后端
   ↓
Dify / Qwen         ← AI 能力
```

Vercel 负责 Web 页面，阿里云 FC 专注 FastAPI、AI 工作流和数据处理。

> 当前代码仍保留 `backend/static/` 同源前端，用于本地运行和兼容旧部署方式；线上版本使用 `frontend/` 中的独立静态前端。

---

## ✨ 核心功能

| 功能 | 说明 |
|---|---|
| 🤖 多智能体计划生成 | Dify 工作流根据工程需求生成施工进度计划 |
| 💬 智能问答 | 通义千问回答施工进度与项目管理问题 |
| 📂 文件分析 | 支持 DOCX / TXT / Markdown 项目资料 |
| 📊 甘特图 | 展示施工任务、工期及关键路径 |
| 👷 资源分析 | 人员配置曲线与设备峰值统计 |
| ✅ QA 检查 | 自动检查计划完整性、日期及逻辑关系 |
| 📈 方案对比 | 支持多个施工计划横向比较 |
| 🧪 Mock 模式 | 无需调用 Dify 即可演示完整工作流程 |

---

## 📁 项目结构

```text
JianCe/
├── frontend/          # Vercel 静态前端
├── backend/           # FastAPI / 阿里云 FC
│   ├── api/           # API 路由
│   ├── core/          # QA、Dify Adapter 等核心逻辑
│   ├── static/        # 保留的本地同源前端
│   └── main.py
├── dify/              # Dify 多智能体工作流 DSL
├── examples/          # 示例施工计划
├── test_inputs/       # 测试输入（施工组织设计文档）
├── test_outputs/      # AI 生成的成品进度计划
├── assets/            # 项目图片
├── requirements.txt
└── README.md
```

### 测试示例说明

| 输入文件 | 项目类型 | 输出文件 | 总工期 |
|---------|---------|---------|-------|
| `test_inputs/test_input_1_办公楼.txt` | 某市高新区科技创新中心办公楼（12层） | `test_outputs/test_output_1.txt` | 305天 |
| `test_inputs/test_input_2_仓库.txt` | 某物流园区3号仓库（钢结构） | `test_outputs/test_output_2.txt` | 95天 |
| `test_inputs/test_input_3_住宅楼.txt` | 佛山市顺德区某住宅小区二期5号楼 | 待生成 | - |

> 📌 **评委提示**：`test_outputs/` 文件夹中包含 AI 自动生成的两份完整进度计划成品，分别对应 `test_inputs/` 中的参数1（办公楼）和参数2（仓库），可直接查看 AI 生成结果的质量与完整性。

---

## 🛠️ 技术栈

**Frontend**

`HTML` · `CSS` · `JavaScript` · `ECharts` · `Vercel`

**Backend**

`Python` · `FastAPI` · `Pydantic` · `HTTPX` · `SSE`

**AI**

`Dify Multi-Agent Workflow` · `通义千问`

**Cloud**

`Alibaba Cloud Function Compute`

---

## 💻 本地运行

```bash
git clone https://github.com/Xiaobai-source-web/JianCe.git
cd JianCe

python -m venv .venv
pip install -r requirements.txt

uvicorn backend.main:app --reload
```

启动后：

```text
Web:     http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs
Health:  http://127.0.0.1:8000/health
```

真实 AI 功能需要自行配置 Dify、通义千问等 API Key。

无 API Key 时，可在对话模式输入：

```text
#mock
```

体验模拟工作流。

---

# 🎯 当前状态与后续开发目标

### 当前已完成

- [x] Dify 多智能体施工计划生成
- [x] FastAPI 后端及 SSE 流式响应
- [x] 通义千问智能问答
- [x] 文件上传与解析
- [x] 施工计划 QA 检查
- [x] 甘特图、关键路径及资源可视化
- [x] 多方案对比
- [x] 阿里云 FC 后端部署
- [x] Vercel 前端部署
- [x] 前后端分离公网访问

### 下一阶段

- [ ] **彻底前后端分离**：移除 `backend/static/` 旧前端，使 FC 成为纯 API 服务
- [ ] **完善工程计算层**：减少对 LLM 直接计算工期、关键路径的依赖，引入确定性算法
- [ ] **增强多智能体协同**：进一步明确计划生成、资源分析、风险分析、监督 QA 等 Agent 职责
- [ ] **完善数据持久化**：增加项目、计划及历史方案数据库
- [ ] **增强文件解析**：支持更多施工组织设计、Excel 等工程文件
- [ ] **完善安全配置**：收紧 CORS、API Key 与生产环境配置
- [ ] **优化云端部署**：完善正式域名、日志、异常监控及服务稳定性
- [ ] **扩展施工管理能力**：进一步探索进度动态更新、资源优化及实际进度偏差分析

---

## 📌 项目说明

本项目经历了从 **FastAPI 前后端一体部署** 到 **Vercel + Alibaba Cloud FC 前后端分离** 的架构调整。

当前版本重点完成了：

> **工程需求 → 多智能体分析 → 施工计划生成 → QA 检查 → 进度与资源可视化**

后续将重点从“功能可用”向 **工程计算可靠性、系统解耦、数据持久化和生产部署能力** 继续完善。