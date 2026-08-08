# 惑梦对话预设可见性与操作收敛 Design

日期：2026-08-08

## 数据模型

- `conversation_preset_overrides.preset_kind` 继续使用文本字段，新增两种语义：
  - `card_prompt`：当前会话锁定角色版本的卡片预设。
  - `global_prompt`：当前会话 runtime profile 实际选中的官方 Prompt 预设。
- 旧 `prompt`/`regex` 行保留兼容读取，但不再暴露到新用户面板；隐藏或不再允许的旧行在运行时被白名单过滤。
- 官方 Prompt 条目新增布尔字段 `user_toggleable`，normalizer 对缺失值固定为 `false`。

## 服务端权威投影

`build_conversation_runtime_config()` 返回：

```text
preset.card_prompt
  preset_id/name/enabled/entries/total/enabled_count

preset.global_prompt
  preset_id/name/enabled/entries/total/enabled_count
```

- 卡片 preset ID 基于当前锁定角色版本和规范化 preset 内容生成稳定指纹，防止跨版本沿用旧覆盖。
- 卡片条目全部进入投影；`toggleable` 仅在有正文、进入顺序表、非 Marker 时为真。
- 官方条目先按当前会话 runtime profile 选择 preset，再过滤 `user_toggleable=true`；不可操作的公开结构项可显示为 locked。
- 投影永不包含 `content`、世界书正文、Regex 正文、Token 或模型配置秘密。

## 保存校验

`save_conversation_preset_overrides()`：

1. 校验会话所有权并读取会话锁定角色版本。
2. 根据 `preset_kind` 重新计算权威 preset ID、允许显示 ID 和允许切换 ID。
3. 要求请求 `preset_id` 精确匹配当前权威 ID。
4. 每个请求 ID 必须属于允许切换集合；隐藏、locked、跨卡和伪造 ID 返回 400。
5. 与默认状态相同则删除 override，否则原子 upsert。
6. reset 只清理当前 kind 和当前会话；响应返回刷新后的 `runtime_config`。

## 生成覆盖

- `chat_context()` 保留 runtime profile 选择结果，并把 `card_prompt` / `global_prompt` 白名单过滤后的 override map 放入 `conversation_settings`。
- `apply_conversation_global_preset_override()` 负责官方 Prompt/Regex；增加 `apply_conversation_card_prompt_override()` 只处理当前卡片 preset。
- `build_user_llm_request()` 在生成 Prompt 消息前应用两类覆盖。
- `prepare_sillytavern_bridge_generation()` 以服务端生成的 provider payload 为基础，将 ST 消息作为对话历史输入，而不是在末尾用原始 ST `messages` 覆盖完整 payload；必需反扒前缀、卡片/官方预设、记忆和数据库提示保持权威。

## 前端 bridge

- 删除 `promptManager` 依赖、`presetRestore` 和 runtimeVariables 中的 `homer_preset_overrides`。
- 面板只读取 `launch.runtime_config.preset`，按“角色卡预设”“官方公开预设”分组渲染。
- 开关调用 `/api/homer/conversations/:conversationId/preset-overrides`，成功后用响应中的 `runtime_config` 替换本地配置。
- locked 条目保留状态和原因，不挂载可写 checkbox。
- 删除 `homer-action-dock` DOM 与 CSS；逐消息 action bar 不变。

## 手机扩展停用

- 默认 `settings.json` 加入 `third-party/st-yuzi-phone`。
- SillyTavern `loadExtensionSettings()` 在 discover/activate 之前强制补入该扩展名，覆盖存量 profile。
- Homer 会话扩展 overlay 默认修正函数也强制保留该 disabled 项，避免旧会话快照把它重新标为启用。

## 验证

- 后端：临时 SQLite + 两个角色版本 + 两个会话 + 两个官方 preset，断言授权、脱敏、隔离、旧 override 清洗和 provider 哨兵。
- Runtime：扩展发现/请求观察、全局 dock DOM 断言、逐消息动作真实生成、面板切换后刷新和第二会话隔离。
- UI：1440×900、390×844 截图与 overflow/console/page-error 断言。
