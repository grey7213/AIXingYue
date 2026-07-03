# 酒馆功能补全 — Design

配套 `tavern-features-requirements.md`。遵循既有架构：单文件 Python stdlib server + Alpine 前端 + extra_settings JSON 扩展模式。

## 1. 数据模型（自动迁移，沿用 `ensure_*` 模式）

### 1.1 `local_apps.extra_settings`（JSON，扩展，不加列）
新增键（与现有 bg_url/nsfw/.../sampling 并列）：
```json
{
  "personality": "性格文本",
  "scenario": "场景文本",
  "mes_example": "示例对话文本",
  "post_history_instructions": "历史后指令(可空)",
  "alternate_greetings": ["备用开场白1", "..."],
  "world_info": [
    {"keys": ["关键词","kw2"], "content": "注入内容", "enabled": true, "constant": false}
  ],
  "creator_notes": "",
  "character_version": ""
}
```
- 写：`normalize_user_app_extras()` 扩展抽取+校验（字符串裁剪、list 规整、world_info 条目结构化）。
- 读：`local_app_to_card()` 展开到顶层字段，供编辑器回填与导出。
- 消费：`call_user_llm()` 用于组装系统提示 + 世界书注入。

### 1.2 `users` 新列（auto-migrate `ensure_user_persona_columns`）
- `persona_name text`
- `persona_desc text`

### 1.3 `messages` 新列（auto-migrate `ensure_messages_columns`）
- `swipes text`  — JSON 数组，assistant 备选回复 `["回复A","回复B"]`
- `swipe_index integer default 0` — 当前激活下标；`content` 始终等于激活 swipe

## 2. 宏替换

`apply_macros(text, char_name, user_name)`：
- `{{char}}` / `{{name}}` → char_name
- `{{user}}` → user_name（persona_name 或默认「你」）
- 同时兼容旧式 `<BOT>`/`<USER>`
- 大小写不敏感，空值安全。应用于：系统提示各段、开场白、备用开场白、世界书 content、mes_example。

## 3. 系统提示组装（重写 `call_user_llm` 的 prompt 部分）

顺序（全部经 `apply_macros`）：
1. pre_prompt（主提示/system）
2. `角色：{name}` + description
3. `性格：{personality}`（有则）
4. `场景：{scenario}`（有则）
5. `关于用户：{persona_desc}`（有则）
6. 命中的世界书条目内容（见 §5）
7. `示例对话：\n{mes_example}`（有则）

→ 作为 system message。随后接对话历史（截断 history_length），末尾若有 `post_history_instructions` 追加为一条 system 消息（接近输出，模拟 ST 的 jailbreak/depth）。
**开场白不再进系统提示**（它已是首条 assistant 消息）。

## 4. 会话与消息流（后端端点）

新增（均在 catch-all 与 `admin/api/` 之前插入，保持路由顺序）：

| Method | Path | 说明 |
|---|---|---|
| POST | `/console/api/web/conversations/start` | body `{app_id,app_name?,app_icon?}` → 建会话并把开场白(+备用)写成首条 assistant 消息(带 swipes)，返回 `{conversation_id, messages:[...]}` |
| POST | `/console/api/web/regenerate` | body `{conversation_id}` → 对最后一条 assistant 消息：基于其前的历史重生成，新结果 append 到该消息 swipes 并设为激活，返回更新后的 message |
| POST | `/console/api/web/messages/<id>/swipe` | body `{dir:"next"\|"prev"}` 或 `{index}`；next 越界则生成新 swipe。返回更新后的 message |
| POST | `/console/api/web/messages/<id>/edit` | body `{content}` → 更新 content（同步当前 swipe），鉴权按 user_id |
| POST | `/console/api/web/messages/<id>/delete` | 删除该消息 |
| POST | `/console/api/web/conversations/<id>/delete` | 删除会话及其消息 |
| GET/POST | `/console/api/web/persona` | 读/存当前用户 persona |
| POST | `/console/api/web/cards/import` | body `{card}` SillyTavern V2 → 建 user 卡，返回卡 |
| GET | `/console/api/web/my-apps/<id>/export` | 返回该卡的 V2 JSON |

Store 新增：`get_message/update_message_content/append_swipe/set_swipe/delete_message/delete_conversation/get_persona/set_persona`。`append_message` 增加可选 `swipes` 参数。

`regenerate/swipe` 复用 `chat_reply_for_app`：取该 assistant 消息之前的历史（到最近的 user 消息），调用同一 LLM 路径。

## 5. 世界书注入

`select_world_info(entries, recent_text)`：
- `constant=true` 的条目恒注入。
- 其余：任一 key 作为子串出现在 `recent_text`（最近若干条消息 + 当前输入，小写）则注入。
- 拼成 `【设定】\n{content}` 段落，去重，限制总长度（如 4000 字）防爆 token。

## 6. SillyTavern Card V2 映射

导入（V2 `data` 或顶层）：
```
name→name, description→description, personality→personality, scenario→scenario,
first_mes→opening_statement, mes_example→mes_example,
alternate_greetings→alternate_greetings, system_prompt→pre_prompt,
post_history_instructions→post_history_instructions,
tags→tags, creator_notes→creator_notes, character_version→character_version,
character_book.entries→world_info（keys/content/enabled/constant 映射）
```
导出：反向产出 `{spec:"chara_card_v2", spec_version:"2.0", data:{...}}`。封面图 URL 放 `data.avatar`（仅 URL，不做 PNG 嵌入）。

## 7. 前端

### 7.1 编辑器 `create.html` / `create.js`（保持 `.editor-*` 组件类）
- 「角色提示词」段新增：性格、场景、示例对话 textarea。
- 新增可折叠组 `备用开场白`：textarea 列表 + 加/删按钮。
- 新增可折叠组 `世界书`：条目列表，每条 = 关键词(逗号分隔)+内容+启用/常驻开关。
- 工具栏「导入」启用：弹文件选择读 JSON → `cards/import` → 跳编辑新卡。新增「导出」按钮（edit 模式）下载 V2 JSON。
- `emptyForm()/payload()/loadExisting()` 同步新字段（遵守 pitfalls #17 三处序列化链）。

### 7.2 聊天 `chat.html` / `chat.js`
- 进入无会话角色 → 调 `conversations/start` 拿开场白首条消息。
- 每条消息 hover 出操作条（沿用现有按钮配色）：assistant=重新生成/编辑/删除 + swipe `◀ i/n ▶`；user=编辑/删除。
- 新回复打字机逐字显现（`typewriter()` 本地定时器，可被新消息打断）。
- 会话列表项加「新建对话」按钮（强制新 conv）与每项删除。
- swipe：`◀`=prev，`▶`=next（末尾触发生成）。

### 7.3 人设 `me.html` / `me.js`
- 增「我的人设」卡片：name + description 表单 → `persona`。

### 7.4 `app-core.js`
新增方法：`startConversation/regenerate/swipeMessage/editMessage/deleteMessage/deleteConversation/getPersona/setPersona/importCard/exportCard`。

## 8. 流式说明

本次用前端打字机模拟 streaming（鲁棒、零 Nginx 风险）。真·SSE token 流为后续阶段，需 `call_user_llm` 流式 + handler flush + 关闭 Nginx proxy_buffering，单列为风险项。

## 9. 风险

- 路由顺序：新 `/console/api/web/*` 必须在 loose matcher（`"model" in normalized` 等）与 catch-all 之前。
- 兼容：`local_app_to_card` 新字段不能破坏 explore/APK（只新增键）。
- token 膨胀：世界书 + 示例对话需限长。
- 迁移幂等：`ensure_*` 仅在列缺失时 ALTER。
- 不回归：开场白移出系统提示只影响 user/admin 卡（upstream 走 proxy，不变）。
