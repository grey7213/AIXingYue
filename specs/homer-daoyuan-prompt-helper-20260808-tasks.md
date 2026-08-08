# 惑梦《道渊》提示词助手与消息头像 Tasks

日期：2026-08-08

| ID | 任务 | 状态 | 验证/备注 |
|---|---|---|---|
| HDY1 | 建立 requirements/design/tasks 并登记导航 | Done | 本组三份 SPEC 已创建并随调查更新 |
| HDY2 | 解析《道渊》PNG 与导入/runtime 投影 | Done | 从 20260801 备份恢复原 PNG；307 世界书、17 Regex、3 个已启用 TavernHelper 脚本；生产存量版本脚本数为 0 |
| HDY3 | 隔离复现“提示词助手”悬浮窗缺失 | Done | 完整夹具下 `#bp-switch-bubble/#bp-switch-panel` 可见且可点击，确认 runtime 可运行、存量数据缺失为主因 |
| HDY4 | 隐藏消息头像并释放消息布局空间 | Done | bridge CSS 隐藏 `#chat .mes > .mesAvatarWrapper`、清零正文 inline padding；桌面/390px wrapper 可见数均为 0 |
| HDY5 | 修复随卡脚本同步或运行兼容 | Done | 从备份恢复 `tavern_helper` 到两张卡、4 个版本和 3 个锁定会话可用的版本快照；不覆盖现有世界书/Regex/Prompt |
| HDY6 | 完成静态、自测和真实 Chromium 回归 | Done | py_compile、Node syntax、repair selftest、原版 ST E2E 桌面/390px、生产两张卡真实浏览器均通过；助手面板可交互、Yuzi 请求 0、console/page/http error=0 |
| HDY7 | 更新 AGENTS、部署、核对哈希、提交并推送 | In Progress | runtime 已发布 release `20260809-000127`，backend/dialogue/Nginx active、8008/8091/public health OK；待提交本地改动并推送；本轮不构建 APK |

## 2026-08-09 验收记录

- 生产目标卡：`user-ba6ddf2528014f46`（200 条规范化世界书）与 `user-48ffc8830b14493c`（199 条），两者均保留 15 条 Regex、恢复 3 个 TavernHelper 脚本。
- 数据修复：4 个历史版本均含 3 个脚本；未发布草稿 0；目标卡会话数修复前后均为 3；SQLite `quick_check=ok`。
- 生产 runtime：桌面/移动真实 Chromium 均显示并可点击提示词助手面板；消息头像 wrapper 可见数 0、正文 inline padding 0、横向溢出 false、Yuzi JS/CSS 请求 0。
- CSS SHA-256：`daf11b8bcc010da52e08e30cfec0488c1a0ddb5486a155c87e299f116ae5b72c`（本地与 `/opt/homer-dialogue-runtime/current` 一致）。
- 回滚备份：`/opt/ai-fengyue-backend/backups/ai_fengyue.sqlite3.daoyuan-helper-20260808-154201.bak`，大小 1,752,850,432 bytes。

## 当前约束

- 不修改或提交 `Tavo_主题效果_14G5y(1).thm`。
- 不启用 `st-yuzi-phone`，不恢复全局操作坞。
- 不把角色脚本、Prompt、世界书、Cookie、Token 或模型 Key 写入公开配置、日志、截图或提交。
