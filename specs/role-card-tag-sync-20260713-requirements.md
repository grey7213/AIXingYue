# 角色卡优化标签同步 Requirements

Updated: 2026-07-13

## 目标

- 将 `E:\obs录制\AI星月-全部公开官方角色卡-8778张-20260710-204132.zip` 中本轮文件名标签同步到线上 `local_apps.tags`。
- 始终通过 Manifest 的 `internal_id` 匹配 `local_apps.id`，不按角色名、顺序或短编号重建角色。
- 文件名标签为 `CLEAR` 的角色不再出现在公开探索或标签查找中。
- 保持用户、会话、消息、收藏、点赞、群聊、记忆等现有记录完整可读。

## 数据规则

- ZIP、Manifest、卡 JSON SHA、internal/display ID 必须全部校验通过。
- 本轮标签以 `cards/<display_id>__<标签表达式>[能力标记].json` 的标签表达式为准；末尾三位 `√/✗` 仍只表示开场、世界书、Regex。
- 百分号转义按 UTF-8 解码，标签去空白、去空值、按大小写不敏感去重。
- `CLEAR` 是删除/归档候选，不写成普通标签。
- 非 CLEAR 卡只修改 `tags`；不覆盖正文、世界书、Regex、提示词、封面、owner、source、display_id 或 updated_at。

## 删除边界

- CLEAR 卡没有任何用户业务引用时，允许物理删除，并同步清理 `role_card_annotations`。
- CLEAR 卡已有会话、消息、收藏、点赞、群聊、记忆、用户标签或日志引用时，保留原 `local_apps.id`，改为非公开归档，避免历史数据失联。
- 不删除任何用户记录，不级联删除 conversations/messages 等表。

## 验收

- dry-run 报告列出标签更新、CLEAR、缺失卡、物理删除、归档保留和全部引用统计。
- 正式写入前使用 SQLite Online Backup，并在事务内重复 preflight。
- 写入后 `pragma quick_check=ok`，非 CLEAR 标签逐卡一致，CLEAR 卡均不在公开搜索范围。
- 线上 backend/Nginx active，内外 `/health` 为 OK，`CONTENT_MODE=local_only`。

## 非目标

- 不改 APK、前端样式、模型配置或用户数据。
- 不恢复 Manifest 中已被独立删除且无法确认应恢复的角色内容。
