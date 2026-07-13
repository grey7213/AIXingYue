# 单会话 Galgame 选项设计

## 数据结构

`conversations` 增加 `galgame_enabled integer not null default 0`。启动时执行兼容迁移，历史会话自动为关闭。

## API

- `POST /console/api/web/conversations/{id}/galgame`
- 请求：`{"enabled": true|false}`，只接受 JSON boolean。
- 响应包含 `conversation_id`、`galgame_enabled`、目标条目 identifier 和 `effective_enabled`。
- 使用 `conversation.id + user_id` 校验所有权；不存在或无权访问统一返回 404。
- 消息列表响应附带当前会话对象，前端以服务端字段为准。

## 运行时提示词覆盖

- 目标 identifier：`21837143-741e-4cc8-8107-b26acacfdee6`。
- 名称兼容：去空白和中英文连接号后匹配 `梦境选项-正常推进`。
- 仅在 `chat_context()` 确认存在当前用户所属普通会话时提供覆盖值。
- `prompt_preset_runtime_blocks()` 仅在开关开启时于内存归一化副本上强制打开目标条目；关闭时不传覆盖，恢复后台预设原始状态；不写回 `api_settings`。
- 普通发送、流式、续写、重新生成和新 swipe 均经过 `chat_context()` 与 `build_user_llm_request()`，因此共享该覆盖。
- 群聊 id 不存在于 `conversations`，不会获得覆盖。

## 前端

- 在聊天右侧设置面板中，于“高级渲染”之后、“收藏”之前加入第 5 个方块按钮。
- 开启时复用 `is-active` 样式；无当前会话或请求处理中禁用。
- 切换会话时立即使用列表中的 `galgame_enabled` 重置状态，消息接口返回后再以服务端权威值覆盖，避免串会话。
- 移动端设置面板限制最大高度并允许滚动。

## 验证

- Python/Node 语法检查。
- 临时 SQLite 验证迁移、持久化、复制、跨用户隔离和不更新 `updated_at`。
- 构造全局预设验证目标条目只在开启会话出现一次，且保持原顺序和 `post_history/user` 位置。
- 浏览器桌面/390px 检查布局、禁用态、开关态和控制台错误。
