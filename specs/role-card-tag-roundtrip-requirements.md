# AI星月角色卡标签往返 Requirements

Updated: 2026-07-10

## 目标

- 从线上 `local_apps` 导出所有公开、已发布的官方角色卡，交给第三方重新标注标签。
- 回传时通过稳定 ID 精确匹配，只完整替换 `local_apps.tags`，不修改角色正文、世界书、Regex、封面、来源、公开状态或所有者。

## 范围

- 导出条件：`source='admin' AND status='published' AND is_public=1`。
- 当前线上预期数量：8778。
- 排除用户创建卡、私有卡和草稿卡。
- 交付完整角色卡包和轻量标签改名包。

## 验收标准

- 每张卡都包含唯一 `internal_id` 与唯一 `display_id`。
- 完整包中每张卡有一份 UTF-8 JSON，保留数据库角色字段与 `extra_settings`。
- 轻量包中每张卡有一个可改名 `.tag` 文件，文件名为 `<display_id>__<标签表达式>.tag`。
- 包内提供只读 Manifest、Manifest SHA-256、UTF-8 BOM CSV 和中文说明。
- 导出数量、唯一 ID 数量、文件数量均一致；未知/重复 ID 为零。
- 生成 ZIP 后计算 SHA-256 并抽样回读 JSON/CSV/文件名。

## 非目标

- 本次不更新线上标签。
- 本次不导出用户私有角色卡。
- 本次不修改或发布 APK。

