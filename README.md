# 施工进度计划智能助手

基于 **FastAPI + Dify 工作流 + ECharts** 的施工进度计划生成与可视化系统。用户通过自然语言描述工程需求，后端调度多智能体 Dify 工作流生成结构化进度计划，并在前端展示甘特图、资源曲线、里程碑与风险分析。

---

## 目录

- [评委快速运行（推荐）](#评委快速运行推荐)
- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [目录结构](#目录结构)
- [环境准备](#环境准备)
- [本地运行](#本地运行)
- [前端使用说明](#前端使用说明)
- [后端 API 简介](#后端-api-简介)
- [Dify 工作流配置](#dify-工作流配置)
- [录屏/演示指南](#录屏演示指南)
- [常见问题](#常见问题)
- [云部署（可选）](#云部署可选)

---

## 评委快速运行（推荐）

> 本节面向评委，提供 **3 分钟内启动项目** 的最简步骤。

### 前置条件

- **Windows 10/11** 或 macOS / Linux 均可
- **Python 3.10+**（推荐 3.12），需加入系统 PATH
- 无需联网，无需任何 API Key（使用模拟模式即可完整演示）

### 第一步：解压项目

将项目压缩包解压到任意目录，例如 `D:\施工进度计划智能助手`。确保目录下有：

```
施工进度计划智能助手/
├── README.md                  ← 本文件
├── .env.example               ← 环境变量模板
├── requirements.txt           ← Python 依赖
├── 多智能体进度系统工程 final.yml  ← Dify 工作流
├── 名创优品.json              ← 内置示例计划
└── backend/                   ← 后端代码
```

### 第二步：创建虚拟环境并安装依赖

打开 **PowerShell** 或 **终端**，`cd` 到项目根目录：

```powershell
# 创建虚拟环境（如果还没有）
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# macOS / Linux:
# source .venv/bin/activate

# 安装依赖
python -m pip install -r requirements.txt
```

> 如果 `python` 命令不可用，请尝试 `python3`。
> 如果遇到权限问题，尝试 `python -m pip install -r requirements.txt --user`。

### 第三步：配置环境变量（可选）

> **如果只需模拟演示，可跳过本步，直接进入第四步启动。**
> 模拟模式（输入 `#mock`）不需要任何 API Key，即可完整展示对话流程、QA 检查和进度看板。

如需真实 AI 生成，需要编辑 `.env` 文件：

```powershell
# 确认项目根目录下有 .env 文件（如没有则从模板创建）：
Copy-Item .env.example .env
```

编辑 `.env`，填入 Dify API Key：

```env
# 【必须填入本项目工作流的 Key】
DIFY_API_KEY=app-xxxxxxxxxxxxxxxx
DIFY_CHATFLOW_URL=https://api.dify.ai/v1/chat-messages
```

> ⚠️ **重要**：此处的 API Key **必须是本项目「多智能体进度系统工程」这个 Dify 工作流的 Key**。
> 其他 Dify 应用的 Key 无法正常工作，因为工作流节点、变量名、输出格式都不兼容。
> 获取方式见下方「Dify 工作流配置」章节。

### 第四步：启动后端

```powershell
python -m backend.main
```

看到以下输出说明启动成功：

```
🚀 FastAPI 后端启动：http://0.0.0.0:8000
```

### 第五步：打开浏览器

| 页面 | 地址 |
|------|------|
| **前端首页** | <http://127.0.0.1:8000/> |
| **API 文档** | <http://127.0.0.1:8000/docs> |
| **健康检查** | <http://127.0.0.1:8000/health> |

### 第六步：使用网页

1. **对话生成**：在对话输入框输入工程需求，点击「发送」
2. **查看看板**：生成完成后，点击顶部「📊 进度看板」
3. **导入方案**：点击「📂 导入计划 JSON」，选择 `名创优品.json` 等文件
4. **方案对比**：勾选「甘特图对比模式」，选择两个方案

---

## 功能特性

1. **自然语言生成进度计划**
   - 输入工程概况、工期、结构形式等，Dify 多智能体工作流自动输出 JSON 格式施工进度计划。

2. **流式响应（SSE）**
   - 对话接口使用 Server-Sent Events，实时返回 AI 文字说明、工作流进度、最终计划与 QA 报告。

3. **本地 QA 检查**
   - 不依赖额外的 Dify QA Agent，后端内置规则 QA，自动检查数据完整性、日期逻辑、工期一致性、关键路径一致性、资源合理性等。

4. **进度看板可视化**
   - 总工期、关键任务数、峰值人数、设备类别等核心指标。
   - ECharts 甘特图（支持全部任务 / 关键路径 / 阶段筛选）。
   - 甘特图双方案对比模式。
   - 主要工种人员配置曲线、设备峰值需求统计。
   - 关键里程碑表格、资源计划摘要、风险与应对措施。

5. **智能问答**
   - 支持与施工进度计划相关的智能问答（需配置千问 API Key）。

6. **历史计划管理**
   - 支持将生成的计划 JSON 导入看板，支持本机历史文件保存与加载。

---

## 技术架构

```text
┌─────────────────────────────────────────────────────────────┐
│                        浏览器前端                             │
│  backend/static/index.html  +  ECharts  +  EventSource(SSE)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────┐
│                     FastAPI 后端                             │
│  backend/main.py                                             │
│  ├── /api/v1/chat/stream   GET  流式生成计划（SSE）           │
│  ├── /api/v1/chat/generate POST 非流式生成计划                │
│  ├── /api/v1/chat/ask      POST 智能问答（千问大模型）         │
│  ├── /api/v1/chat/stream/mock  GET 模拟生成（无需 Dify）      │
│  ├── /api/v1/plan/*        计划校验 / 可视化 / QA            │
│  ├── /api/v1/history/*     历史文件管理                       │
│  └── /api/v1/upload/*      文件上传                           │
│                                                              │
│  backend/core/dify_adapter.py   异步 SSE 包装 Dify 客户端     │
│  backend/core/qa_agent.py       本地规则 QA                  │
│  backend/core/legacy/*          数据解析 / 历史 / Dify 客户端 │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────┐
│                      Dify 平台                               │
│  多智能体进度系统工程 final.yml （38 节点 Chatflow）           │
└─────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```text
.
├── .env.example                          # 环境变量模板（需复制为 .env）
├── .gitignore
├── requirements.txt                      # Python 依赖
├── README.md                             # 本文件
├── 多智能体进度系统工程 final.yml        # Dify 工作流定义文件（导入到 Dify 平台用）
├── 名创优品.json                         # 内置示例进度计划（可用于看板演示）
├── test_input_1_办公楼.txt               # 测试输入示例
├── test_input_2_仓库.txt                 # 测试输入示例
├── test_input_3_住宅楼.txt               # 测试输入示例
├── assets/
│   └── project-logo.svg                  # 项目 logo
├── backend/
│   ├── __init__.py
│   ├── main.py                           # FastAPI 入口
│   ├── config.py                         # 后端配置（读取 .env）
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chat.py                       # 聊天 / 流式生成 / 模拟生成接口
│   │   ├── ask.py                        # 智能问答接口（千问大模型）
│   │   ├── plan.py                       # 计划处理接口
│   │   ├── history.py                    # 历史文件接口
│   │   └── upload.py                     # 文件上传接口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py                     # Pydantic 数据模型
│   │   ├── qa_agent.py                   # 本地规则 QA
│   │   ├── dify_adapter.py              # Dify 异步流式适配器
│   │   └── legacy/                       # 从原 Streamlit 迁移的核心模块
│   │       ├── data.py
│   │       ├── dify_client.py
│   │       └── history.py
│   ├── static/
│   │   ├── index.html                    # 前端单页面应用
│   │   └── vendor/
│   │       └── echarts.min.js            # ECharts 图表库
│   ├── history/                          # 生成的计划自动保存到这里
│   ├── logs/                             # 运行日志
│   └── tests/
│       └── test_api.py                   # 接口测试
└── deploy/
    └── nginx.conf                        # 云部署 Nginx 配置（可选）
```

---

## 环境准备

### 1. Python 版本

需要 **Python 3.10 或更高版本**。检查版本：

```powershell
python --version
```

### 2. 创建虚拟环境（推荐）

```powershell
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Windows CMD:
# .venv\Scripts\activate.bat

# macOS / Linux:
# source .venv/bin/activate
```

### 3. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

主要依赖包括：

| 包名 | 用途 |
|------|------|
| `fastapi` | Web 框架 |
| `uvicorn` | ASGI 服务器 |
| `httpx` | 异步 HTTP 客户端（调用 Dify API） |
| `python-dotenv` | 读取 .env 环境变量 |
| `pydantic` | 数据模型校验 |
| `pandas` | 数据处理 |
| `python-docx` | 解析 Word 文件 |
| `python-multipart` | 文件上传支持 |
| `pytest` | 接口测试 |

### 4. 配置环境变量

项目根目录下已有 `.env.example` 模板文件。如有需要（真实 AI 生成），将其复制为 `.env`：

```powershell
# Windows PowerShell:
Copy-Item .env.example .env

# Windows CMD:
# copy .env.example .env

# macOS / Linux:
# cp .env.example .env
```

> **不需要真实 AI 生成？** 可以不创建 `.env` 文件，直接启动后端使用模拟模式。

`.env` 文件各字段说明：

```env
# ========= Dify 主工作流（真实生成需要） =========
# ⚠️ 必须填入本项目「多智能体进度系统工程」工作流的 API Key
# ⚠️ 其他 Dify 应用的 Key 不兼容，无法正常生成计划
# 在 Dify 平台 → 应用 → API 访问 中获取
DIFY_API_KEY=your-dify-api-key
DIFY_CHATFLOW_URL=https://api.dify.ai/v1/chat-messages

# Dify 超时与重试（通常保持默认）
DIFY_TIMEOUT=1800
DIFY_MAX_RETRIES=3
DIFY_RETRY_INTERVAL=3

# ========= QA Agent（可选，留空则使用本地规则 QA） =========
DIFY_QA_API_KEY=
DIFY_QA_URL=
DIFY_QA_TYPE=chatflow

# ========= 智能问答 - 千问大模型（可选） =========
# 在 DashScope 控制台获取：https://dashscope.console.aliyun.com/
QWEN_API_KEY=your-qwen-api-key
QWEN_MODEL=qwen3.8-flash
QWEN_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

# ========= 服务配置（通常保持默认） =========
HOST=0.0.0.0
PORT=8000
DEBUG=false
CORS_ORIGINS=*
```

---

## 本地运行

### 启动后端

```powershell
python -m backend.main
```

或使用 uvicorn：

```powershell
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后看到：

```
🚀 FastAPI 后端启动：http://0.0.0.0:8000
```

### 验证启动

```powershell
# 浏览器打开
# 前端首页：http://127.0.0.1:8000/
# API 文档：http://127.0.0.1:8000/docs
# 健康检查：http://127.0.0.1:8000/health
```

也可以用命令行测试：

```powershell
# PowerShell:
Invoke-WebRequest http://127.0.0.1:8000/health | Select-Object -ExpandProperty Content
```

### 运行测试

```powershell
python -m pytest backend/tests -v
```

---

## 前端使用说明

### 模式一：对话生成（需要本项目 Dify 工作流的 API Key）

1. 打开首页 `http://127.0.0.1:8000/`，顶部会显示 `Dify 已配置` 状态。
2. 在对话输入框中描述工程需求，例如：

   > 项目为三层框架办公楼，建筑面积 3000 平米，桩基采用预制管桩，合同工期 180 天，请生成施工进度计划。

3. 点击「发送」，右侧会显示工作流节点执行进度与 QA 检查报告。
4. 生成完成后，切换到「📊 进度看板」查看甘特图、资源曲线、里程碑与风险。

> ⚠️ 此模式的 API Key **必须来自本项目绑定的「多智能体进度系统工程」Dify 工作流**，
> 其他 Dify 应用的 Key 不兼容（节点名称、变量名、输出格式不同）。
> 如无此 Key，请使用下方的模拟模式。

### 模式二：模拟演示（推荐评委使用，无需任何 API Key）

> **这是评委演示本项目的推荐方式**，无需 Dify、无需千问、无需联网。

1. 在对话输入框中输入 `#mock` 并点击「发送」。
2. 系统会返回一份内置的模拟施工进度计划，不消耗任何 Token。
3. 右侧实时展示：工作流节点进度条、AI 文字说明、QA 检查报告。
4. 切换到「📊 进度看板」即可查看完整的可视化效果（甘特图、资源曲线、里程碑等）。
5. 也可直接导入 `名创优品.json` 查看看板效果（点击「📂 导入计划 JSON」）。

### 模式三：智能问答

1. 点击顶部「💬 对话生成」旁的「🤖 智能问答」按钮切换模式。
2. 输入与施工进度计划相关的问题即可（需配置 `QWEN_API_KEY`）。

### 看板操作

| 操作 | 说明 |
|------|------|
| **阶段筛选** | 点击「全部任务」/「仅关键路径」/「结构阶段」/「机电与装修」/「收尾验收」 |
| **导入 JSON** | 点击「📂 导入计划 JSON」，选择 `.json` 计划文件 |
| **方案对比** | 勾选「甘特图对比模式」，从下拉框选择第二个方案 |
| **内置示例** | 项目自带「名创优品华南智能配送中心」示例计划，可直接查看 |

---

## 后端 API 简介

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/chat/stream` | 流式生成计划（SSE，EventSource） |
| GET | `/api/v1/chat/stream/mock` | 模拟流式生成（无需 Dify，测试用） |
| POST | `/api/v1/chat/generate` | 非流式生成计划 |
| POST | `/api/v1/chat/ask` | 智能问答（千问大模型） |
| POST | `/api/v1/plan/validate` | 校验计划 JSON 结构 |
| POST | `/api/v1/plan/visualization` | 生成可视化数据包 |
| POST | `/api/v1/plan/qa` | QA 检查计划 |
| GET | `/api/v1/history/list` | 列出历史文件 |
| POST | `/api/v1/upload/files` | 上传并解析文件 |

SSE 事件类型：

| 事件 | 说明 |
|------|------|
| `progress` | 工作流节点执行进度 |
| `answer` | AI 文字说明增量 |
| `plan` | 最终解析出的进度计划 JSON |
| `qa_report` | QA 检查报告 |
| `done` | 流结束 |
| `error` | 错误信息 |

---

## Dify 工作流配置

> 以下步骤**仅在需要真实 AI 生成**时执行。
> 评委如仅需演示看板和交互效果，使用 `#mock` 模式即可，无需执行以下步骤。

### 方式一：使用已部署的现成工作流（推荐）

如作者已将工作流部署到 Dify Cloud，评委只需获取 API Key：

1. 登录 [Dify Cloud](https://cloud.dify.ai)，联系作者获取工作空间访问权限。
2. 打开「多智能体进度系统工程 final」应用。
3. 在应用右上角「API 访问」中获取 API Key（格式为 `app-xxxxxx`）。
4. 将 Key 填入 `.env` 文件的 `DIFY_API_KEY` 字段。

### 方式二：自行部署工作流（需要 Dify 账号）

1. 注册 [Dify 平台](https://dify.ai) 账号（Cloud 或私有化部署均可）。
2. 进入工作空间，点击「创建应用」→「导入 DSL 文件」。
3. 选择项目根目录下的 `多智能体进度系统工程 final.yml`（38 节点 Chatflow）。
4. 根据工作流中的模型节点，配置对应的 LLM API Key（如通义千问、GPT 等）。
5. 如有知识库检索节点，上传相应的施工规范文档。
6. 点击「发布」应用。
7. 在应用右上角「API 访问」中获取 API Key。
8. 将 API Key 填入 `.env` 文件的 `DIFY_API_KEY` 字段。

> ⚠️ **注意**：必须导入 `多智能体进度系统工程 final.yml` 这个工作流，
> 其他 Dify 工作流的 Key 不兼容。原因是后端代码中硬编码了该工作流的
> 变量名（如 `conversation.plan`）、节点名称和输出格式。

---

## 录屏/演示指南

推荐录制以下流程（约 3~5 分钟）：

1. **启动项目**：展示命令行启动后端，浏览器打开 `http://127.0.0.1:8000/`。
2. **模拟生成**（无 API Key 时）：输入 `#mock`，展示 SSE 实时返回的文字、节点进度、QA 报告。
3. **真实生成**（有 API Key 时）：输入一个典型工程需求，展示 AI 实时生成。
4. **进度看板**：切换到看板页，展示：
   - 总工期、关键任务、峰值人数、设备数量指标卡
   - 甘特图与阶段筛选
   - 人员配置曲线、设备峰值图
   - 里程碑表格、资源摘要、风险列表
5. **双方案对比**：导入或生成第二个方案，勾选对比模式，并排展示两个甘特图。
6. **结论**：强调「自然语言 → 结构化计划 → 可视化看板 → QA 检查」的完整闭环。

> 录屏工具推荐：Windows 自带 Xbox Game Bar（Win+G）、OBS Studio、或 ScreenToGif。

---

## 常见问题

**Q：启动后访问首页报错 500？**
A：确认 `.env` 文件位于**项目根目录**（与 `backend/` 同级），而非 `backend/` 内部。如果不需要真实 AI 生成，可以删除 `.env` 文件，使用模拟模式。

**Q：对话没有返回计划？**
A：确认 `.env` 中 `DIFY_API_KEY` 已正确填写，且该 Key 来自**本项目对应的 Dify 工作流**（其他 Dify 应用的 Key 不兼容）。也可输入 `#mock` 测试模拟数据。

**Q：Dify API Key 填了但报错？**
A：必须使用本项目「多智能体进度系统工程」工作流的 Key。其他 Dify 应用的 Key 因变量名和输出格式不同，无法正常工作。请在 Dify 平台确认工作流已发布，且 Key 来自正确的应用。

**Q：甘特图没有数据？**
A：确认计划 JSON 包含 `overview`、`all_tasks_schedule`、`critical_path_tasks` 等字段。可先导入 `名创优品.json` 查看看板效果。

**Q：`python -m backend.main` 报 `ModuleNotFoundError`？**
A：确认已激活虚拟环境（`.venv\Scripts\Activate.ps1`），且在项目**根目录**下执行命令。

**Q：`pip install -r requirements.txt` 报错？**
A：确保 Python 版本 ≥ 3.10，且网络畅通。可尝试加 `--user` 参数：
```powershell
python -m pip install -r requirements.txt --user
```

**Q：Windows PowerShell 提示「无法加载文件 .venv\Scripts\Activate.ps1，因为在此系统上禁止运行脚本」？**
A：执行以下命令后重新激活：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Q：智能问答显示「千问 API Key 未配置」？**
A：需要在 `.env` 中填写 `QWEN_API_KEY`。该功能为可选，不影响进度计划生成。

---

## 云部署（可选）

如需部署到云服务器，可参考 `deploy/nginx.conf` 配置 Nginx 反向代理：

```bash
# 启动后端（服务器后台运行示例）
nohup uvicorn backend.main:app --host 127.0.0.1 --port 8000 > app.log 2>&1 &

# 复制 nginx 配置并 reload
sudo cp deploy/nginx.conf /etc/nginx/conf.d/progress-plan.conf
sudo nginx -t && sudo systemctl reload nginx
```

Nginx 配置要点：

- 将 80/443 端口转发到本地 8000 端口
- 配置 SSE 所需的 `proxy_buffering off` 等参数
- 建议配合 HTTPS 与域名使用

---

## License

本项目仅用于学习交流与竞赛展示。
