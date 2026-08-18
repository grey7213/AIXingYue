# 惑梦（Homer）新服务器迁移需求

## 目标

将 `AIXingYue-main.zip` 解包后的 Web、后端、SillyTavern dialogue runtime 和 APK 产物整理部署到新服务器 `38.76.218.46`，继续使用 `patcher.villainy.top`，并保留同机 CPA/Grok/Sub2API 服务。

## 范围

- 后端：`ai-fengyue-backend.service`，绑定 `127.0.0.1:8008`。
- 对话 runtime：`homer-dialogue.service`，绑定 `127.0.0.1:8091`。
- 前端：`/var/www/ai-fengyue-frontend`，由 Nginx 提供静态文件并代理 API。
- TLS/Nginx：`patcher.villainy.top` 证书、HTTP→HTTPS 和 dialogue 子路径路由。
- APK：保留服务器文件并校验 SHA-256；当前产品开关关闭公网 `/download/` 分发。

## 安全与非目标

- 生产保持 `CONTENT_MODE=local_only`、普通用户 BYOK/支付/任意验证码注册关闭。
- 不导入压缩包中的离线/E2E SQLite，不伪造生产角色库或媒体数据。
- 不删除、重建或改写 CPA/Grok/Sub2API 的 Docker、systemd 或 Nginx 配置。
- 不在文档、日志或回复中输出 API key、token、密码或 SMTP/ZPAY 凭据。

## 验收标准

1. backend、dialogue、Nginx active；8008 健康为 `OK`，8091 只监听 loopback。
2. `https://patcher.villainy.top/health` 返回 200/`OK`，主要页面和 `.mjs` MIME 正确。
3. `/app/open-source.html` 和 `/download/` 明确返回 404。
4. SQLite `pragma quick_check` 为 `ok`，运行数据目录权限符合专用用户约束。
5. TLS SAN 为 `patcher.villainy.top`，DH 参数文件存在，`nginx -t` 通过。
6. 桌面与 390px Chromium 页面无横向溢出、无 page/console error。
7. 同机 CPA/Grok/Sub2API 容器和站点保持可用。
