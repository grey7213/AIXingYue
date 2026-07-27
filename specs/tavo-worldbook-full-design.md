# Tavo / 当前会话运行时配置设计

## 数据边界

新增两张会话级表：

- `conversation_preset_overrides`：按 `user_id, conversation_id, preset_kind, preset_id, entry_id` 保存 Prompt/Regex 条目的布尔覆盖。
- `conversation_worldbook_overrides`：按 `user_id, conversation_id, source_key` 保存世界书条目的 enabled 覆盖和有限字段 patch；`conversation:*` 表示当前会话新增条目。

覆盖记录不写回全局 preset、角色卡、Mod 或不可变版本快照。所有读写先校验 `conversations(id,user_id)`。

## 稳定世界书键

- `required:<id>`：平台必需条目，锁定。
- `mod:<entry-id>`：当前会话所选 Mod 的锁定版本条目。
- `character:<entry-id>:<sequence>`：锁定角色版本条目。
- `conversation:<uuid>`：仅当前会话存在的新增条目。

服务端从锁定角色版本开始，依次应用社区资产、会话 Mod、世界书覆盖；运行顺序保持“平台必需 → Mod → 当前会话新增 → 角色卡”。

## API

- `GET /console/api/web/conversations/{id}/runtime-config`
  - 返回 master 状态、当前 Prompt/Regex 预设条目、分组世界书条目、覆盖状态和统计。
- `POST /console/api/web/conversations/{id}/preset-overrides`
  - 接受 `preset_kind`、`preset_id`、`items[{entry_id,enabled}]`，或 `reset=true`。
- `POST /console/api/web/conversations/{id}/worldbook-overrides`
  - 接受 `items[{source_key,enabled,patch}]`、`replace_entries` 或 `reset=true`。

单次请求限制条目数和 JSON 体积；世界书可编辑字段为名称、关键词、二级关键词、正文、常量/选择性、位置、角色、深度、优先级、顺序、概率、递归、大小写、全词、扫描深度和 sticky/cooldown/delay。必需条目拒绝写入。

## 运行时合并

1. 使用未覆盖的原始 settings 判定模型/provider 路由。
2. 取得普通会话 context 后，复制 Prompt/Regex preset 并应用会话逐项覆盖；`global_preset_enabled=false` 最后关闭整套。
3. 角色 app 副本先应用 Mod，再应用世界书覆盖，不修改数据库中的角色投影。
4. blocking、SSE、continue、regenerate、新 Swipe 共用同一 helper；群聊维持原行为。

## 前端与 iframe RPC

聊天页新增一个 teleport 到 `body` 的悬浮窗，含“预设”和“世界书”页签。会话切换时递增加载序号并清空旧数据，防止异步结果污染新会话。

卡内 bridge 为每个请求生成随机 request id，通过 `xy-tavo-rpc-request` 发给父页。父页只接受当前 DOM 中 `.tavo-frame` 的 `event.source`，再调用当前 Alpine chat controller；返回 `xy-tavo-rpc-response`。方法和参数均为白名单，RPC 不暴露 Cookie、token、父 DOM 或任意 fetch。

## 失败与回退

- API/RPC 失败不影响原生聊天界面，卡内 Promise 收到可读错误。
- 未选择会话时入口禁用，世界书函数返回明确错误而不是静默空数组。
- required 条目、未知 source key、过长正文、过多条目和越权会话均由服务端拒绝。
