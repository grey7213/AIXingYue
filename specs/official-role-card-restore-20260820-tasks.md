# 惑梦官方角色卡完整恢复 Tasks

Updated: 2026-08-20

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| ORC1 | 审计 ZIP、Manifest、目录并集和标签来源 | Done | ZIP CRC 可读；原始 8778；cards 7698 + removed 1080，内部 ID 无交集且并集完整 |
| ORC2 | 审计生产 DB、服务、空间和现有数据 | Done | 服务 active；72G 可用；local_apps=0；users=6；quick_check=ok |
| ORC3 | 建立恢复 SPEC 与 prior-art 结论 | Done | requirements/design/tasks 已建立 |
| ORC4 | 实现并测试事务恢复工具 | Done | 本地副本 8778/8778；版本/注释 8778；quick_check=ok；用户/积分保护不变 |
| ORC5 | 生成并校验目标封面归档 | Done | 8551 文件；425,184,870 bytes；归档 SHA-256 `4b2f4f634e0da3e1195aa654e0b1a88dfa291d85509b3e106e1974a4e24d1d58`；无缺失/不安全路径 |
| ORC6 | 创建生产备份并执行角色恢复 | Done | 生产备份 `/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-official-role-restore-20260819-194035.sqlite3`；quick_check=ok；线上导入 8778 张 |
| ORC7 | 验证数据库、服务、API、封面和浏览器 | Done | API 全库 8778、校园标签 1962、详情/封面 200；桌面/390px 登录态浏览器无 overflow/console/page error；服务与内外 health 正常 |
| ORC8 | 更新 AGENTS/运维记录、提交并推送 | In Progress | 已补充踩坑与恢复记录；待提交本次稳定文件并检查远端推送 |

## 当前发现

- 新服务器角色库为空，但已有 6 个账号；导入必须保护账号及其积分/支付/安全数据。
- 生产媒体缓存目前为空；历史本地素材可匹配 8,551 个站内封面 basename，另有 223 张无封面和 4 张外部封面。
- 不能直接按 `cards/` 文件名编号与隔离目录合并，否则会发生公开编号碰撞。
- 默认 Explore 为纯净区，线上全库仍为 8778；带 `zone=all` 或点击“全库”可查看被纯净区内容词规则隐藏的 242 张卡。
- 2026-08-20 生产导入事务已提交后，旧版恢复脚本在同一 SQLite 连接上执行 post-commit 保护表读取时触发 `sqlite3.DatabaseError: not authorized`；独立只读验证确认数据完整。工具已修复为提交后使用新连接执行保护校验，后续恢复应使用修复版。
