# 无域名部署方案（当前处境：只有 FC 函数，没有域名、没有 DNS 控制台）

> 前提回顾：FC 默认域名会强制注入 `content-disposition: attachment`，浏览器一律下载 HTML。
> 解除这个限制的唯一官方途径是绑定自定义域名——而你现在没有域名。
> 所以只剩下面两条不需要域名的路。

---

## 先说结论：推荐方案 B

| | 方案 A：Cloudflare Workers 反代 | **方案 B：静态托管 + 前端直连（推荐）** |
|---|---|---|
| 前端改动 | **0 行** | 1 行（填后端地址） |
| 网络路径 | 浏览器 → Cloudflare 海外边缘 → 阿里云 | 浏览器 → 阿里云（直连） |
| 国内访问速度 | `workers.dev` 在国内不稳定，可能很慢 | 静态页走 CDN，API 走阿里云国内节点，**快** |
| 长耗时请求 | ⚠️ 免费版对超长连接可能中途断开 | ✅ 直连 FC，超时你自己配（已设 1800 秒） |
| 需要注册 | Cloudflare 账号 | GitHub / Vercel / Gitee 账号 |
| 上手时间 | 5 分钟 | 10 分钟 |

**你的 Dify 工作流耗时可能到几十秒甚至几分钟**（`DIFY_TIMEOUT=1800`），
这种情况下**方案 B 明显更稳**——浏览器直连阿里云，中间没有任何代理层可以超时掐断。

---

## 方案 B：静态托管 + 前端直连（推荐）

### 原理

`content-disposition: attachment` 只影响**浏览器地址栏导航**，**不影响 `fetch()` / XHR**。
JS 拿到的是原始响应体，照常解析 JSON。

所以：**后端 API 继续用 `fcapp.run` 完全没问题**，只需要把 HTML 页面本身放到一个正常的静态托管上。

```
浏览器 ──加载页面──> GitHub Pages / Vercel（静态 HTML，正常 HTTPS）
        ──fetch 调后端──> xxx.fcapp.run（阿里云国内，快）
```

### 我已经改好的文件

```
no-domain-deploy/static-site/
├── index.html              ← 已改造，只需改 1 行
└── vendor/
    └── echarts.min.js
```

改动内容（共 6 处，已全部完成）：

| 改动 | 说明 |
|------|------|
| 注入 `window.API_BASE` | 放在 `<head>` 最前面，带醒目注释 |
| `fetch("/health")` | → `fetch(API_BASE + "/health")` |
| `fetch("/api/v1/chat/ask")` | → `fetch(API_BASE + "/api/v1/chat/ask")` |
| `/api/v1/chat/stream/mock` | → `API_BASE + "/api/v1/chat/stream/mock"` |
| `/api/v1/chat/stream?...` | → `API_BASE + "/api/v1/chat/stream?..."` |
| `fetch("/api/v1/upload/files")` | → `fetch(API_BASE + "/api/v1/upload/files")` |
| echarts 路径 | `/static/vendor/...` → `./vendor/...`（静态托管的相对路径） |

> 设计成 `API_BASE + "/xxx"` 的好处：**如果以后绑了自定义域名、前后端同源，
> 把引号里的内容清空即可，页面自动退回相对路径，不用再改代码。**

### 你要做的 3 步

**第 1 步：填后端地址**

用记事本/VS Code 打开 `static-site/index.html`，改第 13 行：

```html
<script>
  window.API_BASE = "https://你的函数地址.cn-hangzhou.fcapp.run";
</script>
```

（地址在 FC 控制台 → 函数详情 → 触发器 里，去掉末尾的斜杠）

**第 2 步：上传这两个文件到任意静态托管**

推荐顺序（国内访问速度）：

1. **Gitee Pages**（码云）—— 国内最快，免费，需实名认证 + 仓库审核
   - 新建一个公开仓库，传 `index.html` 和 `vendor/` 文件夹
   - 仓库 → 服务 → Gitee Pages → 部署
   - 得到 `https://<用户名>.gitee.io/<仓库名>/`

2. **Vercel** —— 免费，上传即用，国内速度时好时坏
   - 打开 https://vercel.com → New Project → 直接把 `static-site` 文件夹拖进去
   - 得到 `https://<项目名>.vercel.app`

3. **GitHub Pages** —— 免费稳定，但国内访问经常偏慢
   - 新建公开仓库 → 上传文件 → Settings → Pages → 选 main 分支根目录
   - 得到 `https://<用户名>.github.io/<仓库名>/`

> 注意：上传时要保留 `vendor/` 子目录结构，
> 也就是 `index.html` 在根，`echarts.min.js` 在 `vendor/` 下。

**第 3 步：打开页面测试**

访问你拿到的静态地址，应该能看到正常渲染的页面。
输入 `#mock` 可以做离线测试（不消耗 Dify 额度）。

### 跨域问题？不用担心

- 后端 `backend/config.py` 里 `CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")`，默认就是 `*`
- `main.py` 已经挂了 `CORSMiddleware`（`allow_methods=["*"]`、`allow_headers=["*"]`），OPTIONS 预检自动处理
- SSE 流式接口同样支持跨域

如果还是报 CORS，在 FC 环境变量里加一条 `CORS_ORIGINS=*`，然后重新部署。

---

## 方案 A：Cloudflare Workers 反代（备选）

**适合想零改动快速验证的场景，但不建议作为正式演示方案。**

### 原理

在浏览器和 FC 之间加一层 Worker，转发时把 `content-disposition: attachment` 删掉，
于是 `https://xxx.workers.dev` 就是一个正常的 HTTPS 网站，前端**一行不用改**。

### 操作步骤

1. 注册 https://dash.cloudflare.com/ （免费，邮箱即可）
2. 左侧 **Workers 和 Pages** → **创建** → **创建 Worker**
3. 随便起个名字，点**部署**
4. 点 **编辑代码**，把 `cloudflare-worker.js` 的内容**全选替换**进去
5. 改第一行的 `FC_ORIGIN` 为你的 FC 地址
6. 点 **部署**
7. 访问给你的 `https://xxx.workers.dev`

### 风险提示

- ⚠️ **国内访问 `workers.dev` 不稳定**，评委现场可能加载很慢或直接打不开
- ⚠️ **长耗时请求有风险**：你的 Dify 工作流可能跑几十秒到几分钟，
  Workers 免费版对超长连接可能中途断开
- ✅ 免费额度 10 万请求/天，流量本身不是问题

---

## 如果这两个都不满意，还有一条路：花几十块买个域名

全国内最干净的方案其实是：

1. 买个域名（`.top` / `.xyz` 之类首年十几块，阿里云万网或腾讯云都行）
2. **函数迁到中国香港地域**（香港地域绑域名**不需要 ICP 备案**）
3. 按《阿里云FC部署指南（修正版）》8.4 节绑定域名

代价：域名钱 + 重建函数约 20 分钟 + 香港地域网络延迟略高。
好处：得到一个完全属于你自己的、稳定可访问的正式地址，**评委体验最好**。

如果比赛还有几天时间，我建议走这条。
如果明天就要演示，先用方案 B 顶上。
