# 角色卡优化标签同步 Design

Updated: 2026-07-13

## 流程

1. `prepare` 校验 ZIP/Manifest/卡 SHA，并从角色 JSON 文件名解析标签和三项能力。
2. 生成带 ZIP、Manifest 和计划 SHA-256 的不可变 JSON 计划。
3. 在 live SQLite 上 dry-run，按 internal ID 核对现状并统计所有 app_id 引用表。
4. SQLite Online Backup 后进入 `BEGIN IMMEDIATE`，重复 preflight。
5. 非 CLEAR 现存卡仅更新 `tags`；CLEAR 无引用卡删除角色和 annotation；CLEAR 有引用卡保留 ID 并设为私有归档。
6. 回读验证标签、公开范围、引用完整性、SQLite quick_check 和服务健康。

## 引用保护

- 直接引用 `local_apps.id` 的表通过 schema 自动发现：遍历所有表的列，检查 `app_id`、`role_app_id` 等实际列名，并对已知业务表做显式核对。
- `messages` 通过 `conversations.app_id` 间接保护；只要 conversation 引用该卡，就不得物理删除。
- 归档不修改角色 ID，因此历史聊天仍能加载角色详情和继续对话。

## 并发与恢复

- 计划绑定 archive/manifest SHA；apply 必须显式传入预期 plan SHA。
- 标签更新不依赖 7 月 10 日导出时的旧 tags/updated_at，因为线上已经完成过一次标签回填和后续世界书迁移；但事务内必须确认 internal/display ID 未漂移。
- 备份文件禁止覆盖；失败时事务回滚，备份保留用于恢复。
