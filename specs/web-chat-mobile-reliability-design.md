# AI星月 Web 聊天可靠性与沉浸式首页设计

Updated: 2026-07-10

## 路由

- 将当前 `frontend/app/index.html` 的探索内容迁移到 `frontend/app/explore.html`。
- 新 `frontend/app/index.html` 作为轻量入口：检查登录和会话，跳转 `/app/chat.html?conv_id=...` 或 `/app/explore.html`。
- `chat.js` 用 `ai_xingyue_last_conversation_id` 保存最后打开会话。

## 续写接口

- 新增 `POST /console/api/web/chat/continue/stream`，请求字段：`conversation_id`、`model_id`。
- 服务端读取完整会话，要求最后一条消息为 assistant；构造内部续写指令并把完整历史传给模型。
- 生成完成后追加新的 assistant 消息、扣费、刷新摘要，SSE 返回 `start/delta/message_end`。
- 上游为空、截流或规范化后为空时返回 error，不得回退到上一条内容。

## SSE 前端状态

- `sseRequest()` 支持 `AbortSignal`，跟踪 `sawMessageEnd`；EOF 前无结束事件抛 `ApiError`。
- `chatPage` 维护 `_generationSeq`、`_activeAbortController`、`_conversationLoadSeq`。
- SSE 回调校验 generation seq 与 conversation id；`message_end.reply` 无条件作为最终内容。
- visibilitychange 在 replying 时只记录“结束后对账”标记，不刷新数组。

## 聊天布局

- `.chat-immersive-topbar` 固定顶部，使用半透明深色暖黑表面，与现有 AI星月/Fengyue 色板一致。
- 左菜单为抽屉：功能链接 + 当前会话列表；右菜单为弹层：模型选择、记忆、渲染、收藏。
- 移除聊天页 `[data-app-sidebar]` 和 `[data-app-bottom-nav]`，移动端输入框 bottom 只计算 safe-area。
- 角色 hero 在移动端收起为顶部标题，桌面保留紧凑背景带。

## 邮件

- `send_verification_email()` 优先调用 Resend `POST /emails`，Authorization 使用服务端 SMTP password/API key。
- HTTP API 超时控制在 10 秒内；失败时 fallback SMTP。
- 发码 route 在发送成功后才保留验证码；失败时调用 Store 删除本次 purpose/code 记录。

## 探索

- `explore.js` 增加 request seq/AbortController；reset 会使旧响应失效。
- 默认预取必须带同一 seed，或取消无 seed HTML fetch preload，避免同页双请求。
- 新增“换一批”按钮，清除 browse restore 标记并生成新 seed。

## 验证

- Python 函数/API 测试：continue、截流、邮件 fallback、随机 seed。
- Node 语法检查和浏览器 DOM/交互检查。
- 线上临时用户与假上游 E2E；结束后清理测试数据。
