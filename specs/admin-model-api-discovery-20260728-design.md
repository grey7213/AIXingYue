# 惑梦后台模型 API 自动发现与可用性检测设计

## 现状

- 模型节点沿用 `api_settings.model_presets`，一个 preset 代表一个共享 Base URL/API Key 的节点。
- 管理员已可手动增删 preset 和模型文本，但没有 `/models` 自动同步，也没有真实生成检测。
- 用户公开目录由 `public_model_presets()` 从已保存、已启用 preset 展开，并按模型名去重。

## 后端

### 管理员接口

- `POST /admin/api/llm-settings/discover-models`
  - 输入：`preset_id/protocol/base_url/api_key`。
  - 已保存 preset 的新 Key 留空时，从服务端配置复用旧 Key。
  - 请求规范化后的 `/models`，返回候选模型和目录耗时。
- `POST /admin/api/llm-settings/probe-models`
  - 输入：同上，加 `models[]`、`timeout`。
  - 单批最多 12 个模型、最多 6 路并发；前端对较大目录自动分批，避免单个 Nginx 请求超过 120 秒。
  - OpenAI-compatible 使用 `chat/completions`；Anthropic-compatible 使用 `messages`。
  - 使用 `stream=true`、极短提示和小 `max_tokens`，必须取得非空正文才算可用。

### 安全与错误

- 只接受 `http/https` Base URL，去除末尾具体端点，禁止 URL 内嵌用户名/密码。
- API Key 只进入请求头，不进入返回体；错误摘要限制长度并清理可能出现的 Key。
- 探测日志只记录 preset/model/状态/耗时，不记录 Key、提示词或回复正文。
- HTTP、JSON、SSE、空正文、提前截流和超时分别返回稳定状态，不影响站点模型配置。

## 前端

- 将“添加模型预设”文案调整为“新增 API 节点”。
- 每个节点增加：
  - “读取模型目录”：填充 `modelsText`。
  - “检测全部模型”：探测当前模型列表，展示汇总和逐模型结果。
  - “仅保留可用模型”：探测完成后可重复执行；默认探测成功后自动应用可用列表。
- 请求期间按节点显示忙碌状态并禁用重复操作；桌面和移动端按钮允许换行。
- 探测状态是当前页面临时状态，不写入公开配置；真正用户目录仍以点击“保存模型配置”后的 preset 为准。

## 验证

- 本地假 OpenAI 上游覆盖目录、真流式成功、空正文、HTTP 失败和 Key 复用。
- 检查公开模型响应不含 `api_key/base_url/error`。
- Chromium 验证新增节点、自动填充、状态列表、保存以及 1440/390px 无横向溢出和控制台错误。
- 生产部署前备份 SQLite/代码，部署后检查 backend/Nginx、内外 health、`CONTENT_MODE=local_only` 和 SQLite `quick_check`。
