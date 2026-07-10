# AI星月角色卡标注回填与展示 Tasks

Updated: 2026-07-11

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| RCA1 | 全量只读审计 8778 张回传 ZIP | Done | Manifest/ID/JSON/SHA 全通过，异常 0 |
| RCA2 | 明确 filled CSV 与三位能力标记规则 | Done | 6366 replace、2412 skip；8 种组合合计 8778 |
| RCA3 | 实现 prepare/dry-run/apply 安全工具 | Done | `py_compile`、fixture、线上 dry-run 冲突 0 |
| RCA4 | 建立角色能力标注表并扩展列表/详情 API | Done | 列表/详情返回 3 个布尔值；fixture 轻量查询通过 |
| RCA5 | 备份并回填线上标签和能力标注 | Done | 6351 标签实际变化；8778 annotation；逐卡错位 0 |
| RCA6 | 优化 Explore 和角色详情 UI | Done | 375/1440 截图；overflow 0；console error 0 |
| RCA7 | 部署 Web/后端并验证线上状态 | Done | service/nginx active；health OK；CONTENT_MODE=local_only |
| RCA8 | 更新项目记录、提交并推送 | In Progress | 聚焦提交推送 origin/main |

## 已确认审计数据

- 能力组合：`√√√ 3538`、`√√✗ 3865`、`√✗√ 15`、`√✗✗ 1006`、`✗√√ 101`、`✗√✗ 194`、`✗✗√ 1`、`✗✗✗ 58`。
- 主开场 8424；世界书 7698；正则 3655；人工标记与字段检测 100% 一致。
- `√✗✗` 不能自动删除；仅 6 张属于高优先人工复核候选。

## 实际回填结果

- ZIP SHA-256：`0c58f46fd9fb6d2a30d96549bc54a9c9b09f21ff87986e544b427aa8fbe59083`。
- Manifest SHA-256：`12c229d2e34084758e04ac73e46fc22c90582dc355f237e98043bfd628261cff`。
- Plan SHA-256：`7b532ae78cda225f2934d5df55571fd22196700f2c7070ae77d228f768bf4b6a`。
- 线上 dry-run：数据库 8778、计划 8778、冲突 0。
- 线上备份：`/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-role-annotations-20260711-0218.sqlite3`，`quick_check=ok`。
- 正式应用：6351 行标签变化、8778 行标注 upsert；逐卡标签 mismatch 0、annotation mismatch 0。
- 线上 live DB `quick_check=ok`；示例 `0001` 标签为 `重口/NTR/NTL...` 标准组合，能力为 `√√✗`。
- UI 截图：`output/playwright/role-annotations-explore-desktop-final.png`、`role-annotations-explore-mobile-final.png`、`role-annotations-character-desktop-final.png`、`role-annotations-character-mobile-final.png`。
- 角色详情只发起 1 次详情请求；桌面/移动端无横向溢出，Playwright console error 0。
