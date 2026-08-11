# 惑梦消息头与统一流式输出 Design

日期：2026-08-12

## 复用结论

- 继续复用固定 SillyTavern 1.18.0 的 `.ch_name`、`.timestamp`、`.mes_buttons`、原生 `messageEdit()` 和 `StreamingProcessor`，不新建聊天状态机。
- 继续复用 2026-08-09 已完成的 Homer 精确消息菜单；省略号和帮助按钮只作为该菜单的常驻入口。
- 本次是现有 UI 的明确小改与流式回归修复，不需要重新引入第三方实现。

## 消息头结构

`renderMessageMenuTargets()` 在每次消息绘制/更新时幂等装饰原生消息头：

```text
ch_name
  left: name_text + version badge + timestamp + help
  right: more + native edit
```

- 角色名仅做 DOM 展示格式化为 `《名称》`，不改变 `context.chat[].name`。
- 版本优先取卡片 `character_version`，其次取锁定内容版本的 `version_name/version_no`。
- 后端会话 launch 响应补充当前锁定内容版本的非敏感元数据。
- 时间从消息 `send_date` 按浏览器本地时区格式化，原生时间为空时也能稳定展示。
- 编辑状态仍只展示原生保存/取消按钮。

## 交互

- `.extraMesButtonsHint` 在捕获阶段改为打开 Homer 消息菜单，阻止原版隐藏扩展按钮层被展开。
- 帮助按钮同样打开消息菜单，向触屏用户提示完整操作入口。
- `.mes_edit` 保持上游原生事件链；消息头控件加入交互目标白名单，避免长按误触。

## 流式约束

- 抽出 `enforceStreamingConfiguration()`，统一设置 `oai_settings.stream_openai=true` 和 `#stream_toggle`。
- 在连接配置、会话重申、生成动作前和设置更新后重复执行，防止账号设置或扩展重放将其改回阻塞模式。
- 后端 OpenAI-compatible bridge 继续按 `body.stream` 返回 SSE；前端固定请求流式，避免破坏 SillyTavern 对非流式探测的解析约定。
- 生产/离线代理不能只依赖上游响应的 `Content-Type` 判断流式。SillyTavern 的 `forwardFetchResponse()` 可能丢失模型响应的 `Content-Type`，因此 `offline_dev_proxy.py` 对 dialogue runtime 的 `POST /api/backends/chat-completions/generate` 读取请求 JSON；当 `stream: true` 时强制逐块转发、逐块 flush，并在下游补 `text/event-stream`，不得读取完整响应或补 `Content-Length`。
- 上述请求识别限定为 dialogue runtime、固定 POST 路径和严格 JSON 布尔值，避免把普通 API 或静态资源误当作 SSE。

## 验证设计

- E2E 模型桩把每个回答拆成多个 SSE delta，并在 delta 间短暂等待、逐次 flush。
- 浏览器在动作触发后轮询当前角色消息 `.mes_text`，记录生成结束前的不同非空文本快照。
- 对发送、continue、regenerate、next 和位于末候选时的 swipe-right 分别断言至少两次中间增量；swipe-left 只验证既有候选切换。
- 同时断言消息头字段、按钮绑定、桌面/手机安全区和既有菜单/云同步回归。
- 代理单元自测覆盖：目标 runtime/路径/方法/JSON `stream` 严格匹配，以及缺失响应 `Content-Type` 时不缓冲、不生成 `Content-Length`。

## 生产夹具与模型锁定

- 仅给临时角色写 `llm_model` 不足以约束原版 SillyTavern 当前会话；生产验收会同步写入会话级 `homer_model_settings`。
- 触发生成前必须同时断言 `#custom_model_id`、已保存模型 ID 和目标 option 均为临时 preset，避免请求回落站点默认模型。
- 临时模型桩只监听服务器 loopback；验收完成后清理临时用户、角色、内容版本、会话、消息、preset、runtime state、事件回执和 dialogue 用户目录。

## 生产部署与恢复集

- 生产 release：`/opt/homer-dialogue-runtime/releases/20260812-044851`，由 `current` 原子指向。
- 关键哈希：backend `cb0c77723a8fb37e6fd585b2e854f05f0390f352abcbb73c30f4c42552b30117`；bridge JS `1fc7a602ecfd1846a4d79bf48f4ec1b3f3c32df58a4b70e9ad69da307b5827a1`；bridge CSS `ea5b91e318b9686bab927771b9d3d938b591bffd7d74913c9c46b250d975064c`。
- 最近恢复集保留数据库 `ai_fengyue-before-community-versions-20260812-044851.sqlite3`、前端源码 `frontend-source-before-community-versions-20260812-044851.tgz` 和对话数据 `homer-dialogue-data-20260812-044851.tgz`；数据库以 immutable 只读方式 `quick_check=ok`，两个 tar 分别为 130/7914 项。
- 同一源文件的历史 `.bak*` 只保留修改时间最新的一份；旧 release 和旧数据备份目录清空，当前 release 只剩 `20260812-044851`。

## 生产验收结果

- 桌面 `1440×900` 与手机 `390×844` 的消息头字段完整；手机关键词 rail 与消息头几何区域不重叠。
- 发送、续写、重写、下回和 new Swipe 各产生 5 次生成结束前的可见正文更新、7 个流 token 事件，间隔约 110ms；既有 Swipe 左切只切换候选。
- 模型锁定断言为 `customModel=savedModel=codex-hms-*`、目标 option 存在，模型桩确认仅走 loopback。
- 长按/右键/键盘菜单、帮助/更多入口、原生编辑、单条删除、云同步均通过；Yuzi JS/CSS 请求为 0。结果文件中记录的 STMB 两个可选用户文件 404 和页面切换时中止的 `/api/ping` 属已知白名单噪声，未出现 page error 或未预期业务错误。
- 平台许可入口同时保持隐藏：`/app/open-source.html` 为 404，信息页和导航无许可/源码入口。
