# AI星月 SillyTavern 能力补齐设计

Updated: 2026-06-26

## 当前架构

- 前端：静态 HTML + Alpine.js，核心页面在 `frontend/app/`。
- 后端：单文件 Python HTTP 服务 `tools/ai_fengyue_local_server.py`。
- 数据：SQLite `/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3`。
- 部署：`tools/deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`。

## 已落地设计

### 每日签到幂等

- 新增表 `daily_reward_claims(user_id, claim_date, points, created_at)`。
- 主键为 `(user_id, claim_date)`，服务端用北京时间日期 `business_date()`。
- `/console/api/ctf/dailyapppoints` 和 `/console/api/web/rewards/daily` 统一调用 `Store.claim_daily_reward()`。
- 前端 `me.js`、`dashboard-app.js` 根据 `points_added` 显示“签到成功”或“今日已经签到过了”。

### 流式输出基础能力

- 新增 `POST /console/api/web/chat/stream`，返回 `text/event-stream`。
- 事件：
  - `start`: 返回 `conversation_id`。
  - `delta`: 返回文本片段。
  - `message_end`: 返回最终 `message_id`、`reply`、`created_at`。
- 前端 `app-core.js` 增加 `sendChatStream()`，`chat.js` 优先调用流式端点并增量更新 assistant 气泡。
- 2026-06-26 已升级为 OpenAI-compatible 真流式：用户/管理员角色卡调用模型端 `/chat/completions` 时发送 `stream:true`，解析上游 `data:` 中的 `choices[].delta.content` 并透传为前端 `delta` 事件。
- 同步来的上游角色卡仍保留阻塞生成后分块的兼容路径。
- 角色卡保存的是模型预设 ID 时，后端会映射到预设里的真实 `model`，避免把 `default` / `preset-id` 当作模型名发给上游。

### Prompt Manager

- 角色卡 `extra_settings.prompt_blocks` 保存提示词块。
- 每个块支持 `name`、`position`、`order`、`enabled`、`content`。
- `system_before` 注入在角色基础设定前；`system_after` 注入在角色/世界书/示例后；`post_history` 注入在对话历史和用户消息后、生成前。
- 内容支持 `{{char}}` / `{{user}}` 宏替换。
- 管理员可在后台模型配置中维护一个站点级全局 Prompt Preset。导入 SillyTavern preset JSON 时按 `prompt_order` 读取启用项，跳过空 marker；`chatHistory` 前的启用提示作为全局 `system_before`，`chatHistory` 后的启用提示作为全局 `post_history`。该预设应用于所有角色卡，不修改每张卡的本地字段，用户侧不暴露原始预设内容。

### 高级世界书

- 继续把世界书保存在角色卡 `extra_settings.world_info`，兼容旧 `keys/content/enabled/constant` 字段。
- 新增字段：`name`、`secondary_keys`、`selective`、`position`、`depth`、`priority`、`order`、`probability`、`recursive`、`case_sensitive`。
- `position=system` 聚合进系统提示的“相关设定”；`position=post_history` 注入在历史后；`position=depth` 按条目 `depth` 插入到消息历史中。
- 触发规则：常驻条目始终命中；普通条目需命中主关键词；选择性条目或带二级关键词的条目需同时命中主关键词和二级关键词。
- 命中条目按 `priority` 降序、`order` 升序进入预算；`probability=0` 不注入，`100` 必注入；递归条目会把自身内容加入扫描文本以触发后续条目。

### 角色卡 V2/PNG 兼容

- JSON V2 导入/导出继续走 `/console/api/web/cards/import` 和 `/console/api/web/my-apps/{id}/export`。
- PNG 角色卡导入通过前端上传 data URL 到 `/console/api/web/cards/import` 的 `card_file` 字段。
- 后端解析 PNG `tEXt`、`iTXt`、`zTXt` chunk，优先读取 `chara/character/ccv2/ccv3/card/metadata`，支持直接 JSON、URL 编码 JSON、base64 JSON。
- PNG 导出走 `/console/api/web/my-apps/{id}/export-png`，返回包含 `chara` tEXt metadata 的 PNG data URL；前端在创建页提供 PNG 导出按钮。
- V2 字段保真扩展：导入/导出保留 `creator`、`extensions`，世界书高级字段会映射到 Character Book entries。

### 群聊

- 群聊独立于单聊 `conversations/messages`，新增 `group_chats`、`group_members`、`group_messages` 三张表。
- API：
  - `GET/POST /console/api/web/group-chats`：列表 / 创建群聊。
  - `GET /console/api/web/group-chats/{id}`：群详情和消息。
  - `POST /console/api/web/group-chats/{id}/message`：追加用户消息，并默认让下一位角色自动回复。
  - `POST /console/api/web/group-chats/{id}/reply`：指定角色或按当前顺序补一条角色回复。
  - `POST /console/api/web/group-chats/{id}/delete`：删除群和消息。
- 群成员使用角色卡 `app_id`，创建时校验访问权限：公开/官方/同步角色可用，用户私有角色仅本人可用。
- 生成角色回复时复用单聊的模型预设、Persona、世界书和 Prompt Manager；群消息会转成带发言人前缀的 LLM history，并要求目标角色只以自己身份发言。
- 前端新增 `/app/group-chat.html`，支持角色搜索、添加成员、创建群、群消息流、自动下一位回复、手动指定角色发言和删除群。

### 用户 BYOK / 多供应商连接器

- 站长模型预设继续保存在 `api_settings`，用户自带 Key 单独保存在 `user_model_presets`，避免把用户 Key 写入角色卡或管理员配置。
- 模型连接器新增 `protocol`，支持 `openai` 和 `anthropic`。旧数据默认按 OpenAI-compatible 处理，避免破坏已配置的 OpenRouter/DeepSeek/中转。
- API：
  - `GET /console/api/web/provider-templates`：返回 OpenAI-compatible、OpenRouter、DeepSeek、Moonshot、Anthropic/Claude、自定义 OpenAI-compatible、自定义 Anthropic-compatible 模板。
  - `GET/POST /console/api/web/user-model-presets`：读取/保存当前用户自己的模型连接器。
- 用户模型响应只返回 `has_api_key` 与 `api_key_preview`，不回显明文 Key。
- 角色卡的 `llm_model` 可保存为 `user:<preset_id>`；聊天时 `effective_llm_settings(app, user_id)` 会读取当前登录用户自己的 preset 和 Key。
- 如果其他用户打开一张引用 `user:<preset_id>` 的公开角色卡，但自己没有对应 preset，则不会拿到原作者 Key，会回退到站点默认模型。
- 前端“我的”页新增“我的模型连接器”；创建页模型下拉合并站点模型和当前用户可用的“我的模型”。
- OpenAI-compatible 调用 `/chat/completions`，Header 使用 `Authorization: Bearer ...`；Anthropic-compatible 调用 `/messages`，Header 使用 `x-api-key` 和 `anthropic-version`，并把 system prompt 放在顶层 `system` 字段。
- 管理员后台模型预设也支持 `protocol` 和一组模型列表；用户创建角色时看到展开后的「供应商 / 模型」条目，聊天时后端把内部选择 ID 还原为真实模型名。

### 长期记忆与自动摘要

- 新增 `chat_memories` 表保存用户长期记忆，字段包括 `app_id`、`title`、`content`、`keywords`、`enabled`、`pinned`、`last_used_at`。
- 新增 `conversation_summaries` 表保存单聊会话摘要，按 `conversation_id` 一条摘要。
- API：
  - `GET/POST /console/api/web/memories`：当前用户按角色读取/保存记忆；角色记忆和全局记忆会一起返回。
  - `POST /console/api/web/memories/{id}/delete`：删除当前用户自己的记忆。
  - `GET/POST /console/api/web/conversations/{id}/summary`：读取、手动保存或 `auto:true` 自动生成当前会话摘要。
- 记忆筛选：`pinned` 记忆始终注入；带关键词的记忆在最近历史/新消息命中关键词时注入；无关键词记忆做弱文本匹配。
- `build_user_llm_request()` 新增 `context` 参数，把 `【对话摘要】` 和 `【长期记忆】` 作为独立 system 消息插在角色系统提示之后、聊天历史之前。
- 普通阻塞聊天、流式聊天、重新生成和 swipe 新回复共用同一套记忆/摘要注入链路。
- 聊天完成后当消息数达到阈值会自动刷新摘要；用户也可在聊天页记忆抽屉手动触发自动摘要。
- 前端 `/app/chat.html` 新增“记忆”抽屉，用于当前会话摘要、自动摘要、添加/删除当前角色记忆。

### 媒体与扩展能力

- 角色卡 `extra_settings` 新增：
  - `quick_replies`：快捷回复按钮，字段为 `label`、`message`、`enabled`、`order`。
  - `regex_scripts`：回复后处理脚本，字段为 `name`、`find`、`replace`、`flags`、`enabled`、`order`。
- 角色创建/编辑页“高级提示词”折叠区可配置 Quick Reply 与 Regex。
- 角色详情 API 会回传 `quick_replies` 和 `regex_scripts`，前端聊天页加载角色后渲染可点击的 Quick Reply 按钮。
- 点击 Quick Reply 会直接走现有 `sendMessage()` 流式聊天链路。
- Regex 在后端执行。阻塞聊天会在返回前处理回复；流式聊天如果角色启用 Regex，会先缓冲上游流式文本、执行正则替换，再把处理后的文本分块发给前端和保存。
- 聊天页媒体能力：
  - assistant 消息操作条提供浏览器 Web Speech `speechSynthesis` 朗读。
  - 输入框提供浏览器 Web Speech `SpeechRecognition/webkitSpeechRecognition` 语音输入。
  - `/app/image-chat.html` 继续使用现有 `/console/api/web/image-chat` 占位接口记录图片聊天请求；接入真实图片模型前不伪造生成结果。

## 后续设计方向

- 后续可把图片聊天占位接口升级为真实多模态/图片生成供应商连接器。
