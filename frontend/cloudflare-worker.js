/**
 * Cloudflare Worker —— 反向代理阿里云 FC 函数，去掉强制下载响应头
 *
 * 作用：阿里云 FC 默认域名（*.fcapp.run）会强制注入
 *       content-disposition: attachment，导致浏览器把 HTML 当附件下载。
 *       本 Worker 转发请求时把这个响应头删掉，
 *       于是你可以用 https://xxx.workers.dev 正常打开网页。
 *
 * 优点：前端一行代码都不用改，前后端同源，无跨域问题。
 * 免费额度：10 万请求/天，演示足够。
 *
 * ─────────────────────────────────────────────
 * 部署前【只改下面这一行】：换成你的 FC 函数公网地址（不要带结尾斜杠）
 * ─────────────────────────────────────────────
 */

const FC_ORIGIN = "https://YOUR-FC-ADDRESS.cn-hangzhou.fcapp.run";

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // 1) 处理 CORS 预检（OPTIONS），省得再回源
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": request.headers.get("Origin") || "*",
          "Access-Control-Allow-Methods":
            "GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS",
          "Access-Control-Allow-Headers":
            request.headers.get("Access-Control-Request-Headers") || "*",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    // 2) 转发到 FC，路径和查询串原样带上
    const target = FC_ORIGIN + url.pathname + url.search;

    const headers = new Headers(request.headers);
    headers.delete("host"); // 必须删，否则 Host 会串成 workers.dev

    const upstream = await fetch(target, {
      method: request.method,
      headers: headers,
      // GET / HEAD 不能带 body，否则 fetch 会抛错
      body: request.method === "GET" || request.method === "HEAD"
        ? undefined
        : request.body,
      redirect: "follow",
    });

    // 3) 构造新响应（这样 headers 才是可写的）
    const response = new Response(upstream.body, upstream);

    // 4) 关键一步：删掉 FC 强制加的 content-disposition: attachment
    response.headers.delete("content-disposition");

    // 5) 顺手补个宽松的 CORS，方便你在别处调试
    const origin = request.headers.get("Origin");
    if (origin && !response.headers.has("access-control-allow-origin")) {
      response.headers.set("access-control-allow-origin", origin);
      response.headers.set("vary", "Origin");
    }

    return response;
  },
};
