# 惑梦官方角色卡完整恢复 Design

Updated: 2026-08-20

## 输入审计

- ZIP SHA-256：`b2891294bb25d2ad7cbae83494e54fa1eee668d251ad804af438333038ee808d`。
- 原始 Manifest：8,778 张；内部 ID 与公开编号均唯一。
- 最终活动目录 `cards/`：7,698 张。
- 隔离目录 `removed-cards-refinement/`：1,080 张。
- 两目录按内部 ID 无交集、并集恰好为 8,778 张；因此恢复完整库时按内部 ID 合并，而不按文件名编号合并。
- 最终活动目录做过连续重排，不能直接拿其 `record.display_id` 与隔离目录拼接；生产公开编号统一回取原始 Manifest。

## Prior art 与选型

- 复用项目内 `export_role_cards_for_tagging.py` 的 Manifest/稳定 ID 规则、`import_role_card_annotations.py` 的特征检测与 SQLite Online Backup 思路，以及历史远端批量导入脚本的字段映射。
- 调研了活跃的 Apache-2.0 项目 `simonw/sqlite-utils`（2026-08-14 仍有提交）和 `benbjohnson/litestream`（2026-08-19 仍有提交）。前者适合通用 SQLite ETL，后者适合持续复制；本次是一次性、项目专属、需要严格跨表事务与内容哈希的恢复，额外依赖会扩大部署面，因此采用 Python 标准库 `sqlite3` 与现有项目 schema。

## 恢复工具

- 新增 `tools/restore_official_role_cards.py`：
  - `prepare`：只读校验 ZIP、生成不可变计划和 dry-run 摘要。
  - `apply`：校验计划哈希、目标 DB 冲突、备份路径与业务表基线后，在单个 `BEGIN IMMEDIATE` 事务内导入。
  - `verify`：回读数量、编号、标签、版本、注释、引用完整性和 `quick_check`。
- 计划记录每张卡的内部 ID、原始公开编号、来源成员、记录 SHA-256、标签及特征，不复制正文到计划文件。

## 数据写入

- `local_apps`：保留交付内容字段；强制官方/公开/已发布；公开编号取原始 Manifest。
- `content_versions`：为每张卡建立确定性 `cver_...` 基线版本，快照格式与 `card_version_workshop.py` 一致。
- `role_card_annotations`：写入 `has_opening`、`has_world_info`、`has_regex`。
- 不改其他业务表；应用前后记录用户、积分、支付、订单、会话、模型配置等保护表计数与摘要。

## 封面恢复

- 按交付 `cover_url` 的 basename 建立本地索引，来源包括历史三个导入批次的 cover 目录/归档。
- 生成只包含目标封面的扁平 `cover/` 归档并上传到 `/var/www/ai-fengyue-frontend/media-cache/cover/`。
- 解包前校验归档路径只能是安全的普通文件名；解包后按计划逐项检查存在性。

## 部署顺序

1. 本地 prepare、覆盖关系和封面索引验证。
2. 远端 SQLite Online Backup 并回读 `quick_check`。
3. 上传 ZIP、恢复工具、计划和封面归档，逐个校验 SHA-256。
4. 在短维护窗口停止 backend，复核 DB 基线，执行事务导入；成功后启动 backend。
5. 验证数据库、服务、API、封面和浏览器；失败时恢复已验证备份并重启服务。

## 实际上线结果（2026-08-20）

- 生产数据库备份：`/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-official-role-restore-20260819-194035.sqlite3`，备份 `quick_check=ok`，恢复前 `local_apps=0/users=6`。
- 生产导入后：公开已发布官方角色 `8778`，公开编号连续 `0001`–`8778`；独立只读 verify 的行、编号、版本和注释 mismatch 均为 `0`，live `quick_check=ok`。
- 封面：服务器 `media-cache/cover` 已部署 `8551` 个本地文件；无封面 223 张、外部 URL 4 张保持原交付状态。
- 公开 API：全库 `8778`，`校园` 标签 `1962`；默认纯净区 `8536`，切换“全库”可查看全部角色。
- 浏览器：登录态 Chromium 在 1440×900 与 390×844 检查 Explore，console/page error 为 0、横向溢出为 0。
- 服务：backend、homer-dialogue、Nginx active，内外 `/health` 返回 `OK`，`CONTENT_MODE=local_only` 保持不变。
