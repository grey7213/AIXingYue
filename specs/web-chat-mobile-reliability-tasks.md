# AI星月 Web 聊天可靠性与沉浸式首页任务

Updated: 2026-07-10

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| WMR1 | 现状与线上日志核对 | Done | 已确认续写复用 regenerate/swipe、SSE 竞态、同步 SMTP、随机请求双发/旧请求覆盖风险 |
| WMR2 | 新增真正的 SSE AI续写接口 | Done | 本地后端 E2E：完整历史续写、追加 assistant、扣 50、无隐藏 user 气泡 |
| WMR3 | 修复 SSE 截流、旧消息覆盖和串会话 | Done | RST 截流不落库/不扣费；浏览器无 `message_end` 显示明确错误，不回显旧回复 |
| WMR4 | 优化验证码发送链路 | Done | 线上 Resend HTTPS 已接受测试邮件；失败回退 SMTP，最终失败删除验证码 |
| WMR5 | 修复探索随机请求并增加换一批 | Done | AbortController + epoch；本地/线上连续换批角色集合发生变化 |
| WMR6 | `/app/` 进入上次会话，迁移探索页 | Done | 本地和线上均恢复 localStorage 指定的最后会话；无会话进入探索 |
| WMR7 | 聊天固定顶部双菜单，隐藏底栏 | Done | 430x932/1440x900 Playwright；顶部左右菜单可用，无全局 sidebar/bottom nav |
| WMR8 | 部署、health、回归与清理 | Done | `--skip-apk` 部署；backend/nginx active，health OK，APK 下载仍 404，CONTENT_MODE=local_only |
| WMR9 | 更新 AGENTS/current-state、提交并推送 | Done | 项目规则和续接状态已更新；聚焦提交并推送 origin/main |

## 当前发现

- `/regenerate` 和末条 swipe-new 都排除目标 assistant，再复用上一条 user 输入，因此不是续写。
- `sseRequest()` 在未收到 `message_end` 时也会正常返回；前端收到部分 delta 后忽略 `message_end.reply`。
- visibilitychange 会在生成中刷新并替换 `messages`，使流式闭包持有的 replyMsg 失联。
- 邮件使用同步 SMTP，每次都重新连接、STARTTLS、登录和发送。
- 探索页存在无 seed preload 与带 seed JS 请求双发；reset 时旧请求仍可写入。

## 完成验证

- `D:\Anconda3\python.exe -m py_compile tools\ai_fengyue_local_server.py`
- `D:\Anconda3\python.exe output\verify_backend_mobile_reliability_local.py` → `PASS`
- `D:\Anconda3\python.exe output\verify_web_chat_mobile_reliability_static.py` → `PASS`
- `node output\playwright-node\verify_web_chat_mobile_reliability.mjs` → 续写、截流、双菜单、上次会话恢复全部通过
- `node output\playwright-node\verify_web_chat_reliability_live.mjs` → 线上恢复会话、顶部菜单、探索换批通过，0 console/page error
- 线上：`ai-fengyue-backend.service`/`nginx` active，`/health` OK，`CONTENT_MODE=local_only`，`/download/ai-xingyue-latest.apk` HTTP 404
