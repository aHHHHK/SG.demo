# 本机后端 + Cloudflare 免费临时隧道

## 初次准备

1. 下载 Cloudflare 官方 Windows amd64 客户端：
   https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
   放到项目的 `tools/cloudflared.exe`。仅适用于 x64 Windows。
2. 将更新后的 `web` 目录重新部署到原 Vercel 项目，保持原来的静态网站配置。
   不要把 logs、Python 环境、隧道工具上传到前端。
3. 在项目目录打开 PowerShell，执行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\start_online.ps1
   ```

   如果 Python 不在默认位置，用 `-Python "实际的python.exe路径"` 指定。

4. 终端显示随机访问码和 `https://xxx.trycloudflare.com` 地址。
   在 Vercel 网页顶部填入这两项，点击“保存并连接”。
   地址不要加 `/api`。访问码不要提交到代码仓库或写进前端文件。

## 每次演示

启动脚本，更新网页里的隧道地址和访问码。保持电脑开机、联网，禁止演示期间自动睡眠。
关闭终端或 Ctrl+C 会停止服务；后端重启会清空现有仿真会话。
修改了 Python 文件时也需要重启后端。

访问码只保存在当前浏览器标签页的 sessionStorage；新标签页需要重新填写。
后端地址保存在当前浏览器的 localStorage。只向可信演示者提供访问码。
请求来自其他网站会被拒绝；同一时间只允许一个计算请求，忙时返回 429。
这不是多用户生产服务；有访问码的人仍共享计算资源，需要轮流操作。

## 排查

- 没有顶部连接栏：Vercel 还是旧版前端，重新部署 web 目录并刷新。
- 后端地址的 `/api/health` 应返回 JSON，status 为 ok。它不需要访问码。
- 401：访问码错误或后端已经重启。
- 403：前端域名不匹配；启动脚本用 `-FrontendOrigin 'https://你的正式域名'` 指定。
- 429：其他请求正在计算或会话数量已达上限，请稍后再试。
- 隧道连接失败：检查网络和 cloudflared 输出；日志在 logs/online-*。
- 浏览器连接失败但 health 正常：在开发者工具 Network 检查 OPTIONS 和 POST。
  跨域授权只允许精确配置的前端域名，不包含 Vercel 的其他预览域名。

临时隧道没有可用性保证，地址变化、网络中断或服务限制可能影响演示。
隧道也会暴露 web 目录中的静态页面，但不暴露项目根目录和模型源码。
无需开放路由器入站端口；后端保持只监听 127.0.0.1。
