# 角色卡优化标签同步 Tasks

Updated: 2026-07-13

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| RTS1 | 校验新 ZIP 和稳定 ID | Done | ZIP 8778 张；internal/display ID 唯一；卡 SHA 全通过 |
| RTS2 | 明确本轮文件名标签与 CLEAR 语义 | Done | 旧 CSV 未包含新改名；文件名为本轮来源；CLEAR 318 张 |
| RTS3 | 审计线上角色和用户引用 | Done | CLEAR 318：306 无功能引用，12 张关联 16 会话/72 消息/2 收藏 |
| RTS4 | 实现 filename-tag prepare/dry-run/apply 工具 | Done | `py_compile`、8778 卡 prepare、live dry-run 冲突 0 |
| RTS5 | 备份并执行标签同步/安全删除归档 | Done | 8318 标签更新、306 删除、12 私有隐藏 |
| RTS6 | 验证数据库、公开搜索和服务健康 | Done | live/backup quick_check ok；业务表行数不变；health OK |
| RTS7 | 更新项目记录并提交推送 | Done | 聚焦提交，仅包含同步工具、SPEC 与项目规则 |

## 已确认输入

- ZIP SHA-256：`5207d9c02170bd1a19a86ce4c20a2df89497e44bba01ab9e85a4beb177bd0ba1`。
- Manifest SHA-256：`12c229d2e34084758e04ac73e46fc22c90582dc355f237e98043bfd628261cff`。
- 新 ZIP 含 `_rename_map.txt` 332 项；旧 `tag-overrides.filled.csv` 仍是上一轮结果，不能作为本轮唯一标签来源。

## 实际应用结果

- Plan SHA-256：`e6874451a0b3599729553387bfc313489e2864cd0956eeee7bd9655ff7671850`。
- 线上预检：8775/8778 张仍存在，3 张在导出后已独立删除且未恢复；冲突 0。
- 正式备份：`/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-filename-tags-20260713-015045.sqlite3`，大小 1454579712 bytes，`quick_check=ok`。
- 正式写入：8318 张现存非 CLEAR 卡标签变化；306 张无功能引用 CLEAR 卡物理删除；12 张有引用 CLEAR 卡保留 ID、清空标签并设 `is_public=0`。
- 用户数据保护：conversations 380、messages 1687、user_favorites 36，及摘要/记忆/群聊/点赞/用户标签/评论表行数前后不变。
- 最终 DB：`local_apps=8486`、admin=8471、公开已发布 admin=8456、公开官方空标签=0；live DB `quick_check=ok`。
- 服务：backend/Nginx active，内外 `/health` 为 OK，`CONTENT_MODE=local_only`。
