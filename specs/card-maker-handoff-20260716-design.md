# 制卡器交接功能设计（2026-07-16）

## 模型目录与价格

- 在 `api_settings.model_presets` 追加稳定 preset `gemini`，Base URL 沿用已实测兼容的 CelestiAI OpenAI 接口，密钥仅保存在线上 SQLite。
- 模型列表来自该密钥的 `/models` 实测结果：`gemini-2.5-flash-cli`、`gemini-2.5-flash-lite-cli`、`gemini-3-flash-cli`、`gemini-3.1-pro-cli`、`gemini-3.1-pro-high-cli`、`gemini-3.1-pro-low-cli`。
- 保留现有默认 preset；公开模型项增加 `points_cost` 与 `price_label`，值由 `CHAT_MESSAGE_COST` 动态生成。
- 聊天页按 `preset_id` 分组；创作页使用 optgroup，组名来自 preset 名称。

## 反扒世界书

- 数据库只保存作者世界书；导入/保存时删除 `tavo-anti-scrape-v2` 及同策略伪造条目。
- `local_app_to_card()`、管理员详情和 V2/PNG 导出只返回作者世界书，并返回布尔提示 `platform_worldbook_applied=true`。
- `app_extras()` 在每次生成时从服务端私有文件重新调用 `ensure_required_world_info()`；任何角色/会话开关都不能关闭平台必需世界书。
- 修复 partial update：只有 payload 明确含 `world_info` 时才覆盖作者世界书。

## 本卡预设

- `extra_settings.card_prompt_preset` 保存白名单字段：`version/enabled/name/format/source_file/prompts/prompt_order/blocks/stats`。
- 普通创作者导入后默认关闭，必须显式开启；未知字段、provider、header、API Key 等一律丢弃。
- 运行时复用 Prompt Preset block 解析，分别注入 `system_before/system_after/post_history`。
- 本卡预设与站点全局预设独立；会话关闭全局预设只关闭站点 Prompt/Regex，不关闭本卡预设。
- V2 扩展命名空间为 `data.extensions.homer_card_prompt_preset`。

## 互动素材

- 新增 `tools/card_experience_extension.py`，使用 `LocalObjectStorage(MEDIA_DIR/card-assets)`。
- 新增 `card_media_assets` 表；服务启动执行轻量建表/索引和过期草稿清理。
- 用户路由：upload-intent、PUT content、complete、delete。二进制 PUT 在 JSON body 解析前处理。
- 创建/更新卡时由服务端 `bind_payload()` 重建可信 `media_assets/world_info/card_experience`，客户端 URL 不作为权威。
- 详情从可信 extra snapshot 返回；删除素材同步清除世界书、默认 BGM 与规则引用；删除角色回收素材。
- 前端复用 ZIP 中 schema/runtime/editor 实现；运行时使用 Shadow DOM、白名单声明式动作、无作者脚本。

## 高级创作权限

- `users` 增加 `advanced_creator_override integer not null default 0`；管理员只控制白名单，不修改农场数据。
- 农场全解锁沿用权威规则：`farm_profiles.streak_days >= 49`，即 `FARM_PLOT_UNLOCK_DAYS` 的 8 个阈值全部满足。
- 访问结果包含 `allowed/source/farm_unlocked/admin_override/streak_days/unlocked_plots/required_days`。
- 用户 API `GET /console/api/web/creator-access`；管理员 API `POST /admin/api/users/{id}/advanced-creation`。
- upload-intent 及保存实际高级字段时服务端强制校验；complete/delete 允许完成或清理既有对象。
- 创作页未开放时保留基础制卡，互动界面和本卡预设显示解锁说明；payload 不提交高级字段。聊天运行时不因创作者后续失去权限而破坏已发布卡。

## 部署与数据迁移

- 部署 helper 同时上传后端扩展模块。
- 部署前备份主 SQLite、后端和相关前端文件。
- 离线/受锁事务清理存量角色 extra_settings 中的平台反扒副本，不改作者条目、角色 ID 或业务关联。
