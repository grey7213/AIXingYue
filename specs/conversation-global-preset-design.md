# 单会话全局预设开关设计

## 数据结构

`conversations` 增加 `global_preset_enabled integer not null default 1`。启动时执行兼容迁移，历史会话自动保持现有“应用全局预设”行为。

会话读取、列表、消息接口和复制操作统一返回布尔字段 `global_preset_enabled`；复制会话继承原值，新会话默认 `true`。

## API

- `POST /console/api/web/conversations/{id}/global-preset`
- 请求：`{"enabled": true|false}`，只接受 JSON boolean。
- 响应包含 `conversation_id`、`global_preset_enabled`、全局 Prompt/Regex 的实际启用状态和 Galgame 实际状态。
- 使用 `conversation.id + user_id` 校验所有权；不存在或无权访问统一返回 404。
- 更新设置不修改 `conversations.updated_at`，避免切换开关改变历史列表排序。

## 运行时覆盖

- `chat_context()` 只对真实普通会话写入 `conversation_settings.global_preset_enabled`；群聊 id 不在 `conversations`，因此不获得覆盖。
- 运行时 helper 浅复制有效模型设置。关闭时仅把副本中的 `global_prompt_preset` 和 `global_regex_preset` 置为 disabled，不写回 `api_settings`。
- 模型/provider 路由仍使用原始模型设置判断；会话覆盖只在构造请求、流式缓冲判断和回复后处理前应用，避免旧 upstream 角色因关闭全局预设意外切换调用路径。
- blocking、SSE send、continue、regenerate 和 new swipe 全部使用同一 helper。
- 全局关闭优先于 Galgame 运行时覆盖；Galgame 存储值不清除。

## 前端

- 在聊天右侧设置面板中，于“Galgame 选项”后增加第 6 个方块，保持现有 3 列布局，形成 3×2。
- 默认显示“关闭全局预设”；关闭后使用 `is-active` 粉色状态并显示“已关闭预设”。
- 无当前会话或请求处理中禁用。
- 切换会话时先使用列表状态，消息接口返回后再以服务端权威字段覆盖，避免异步请求污染新会话。

## 验证

- Python/Node 语法与 Git 差异检查。
- 临时 SQLite 验证旧库迁移默认值、所有权、复制继承、会话隔离和 `updated_at` 不变。
- 构造全局 Prompt/Regex 哨兵验证关闭/恢复、角色 Regex 保留、全局 Regex 缓冲解除和 Galgame 优先级。
- 本地 HTTP API 验证严格 boolean、跨用户 404、列表/消息持久化。
- 线上 API、数据库、服务健康和 390px/桌面浏览器验收。
