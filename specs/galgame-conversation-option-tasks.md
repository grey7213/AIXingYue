# 单会话 Galgame 选项任务

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| GG1 | 建立需求、设计与任务 SPEC | Done | 本目录三个 Galgame SPEC 文件 |
| GG2 | 增加会话字段、迁移、读写和复制语义 | Done | 本地旧库迁移、复制继承、`updated_at` 不变验证通过 |
| GG3 | 增加鉴权 API 与消息/新会话状态返回 | Done | 本地与线上严格 boolean、跨用户 404、刷新持久化通过 |
| GG4 | 增加全局预设目标条目的单会话运行时覆盖 | Done | 线上真实预设运行块 `28 -> 29`，目标仅 1 次且为 `post_history/user` |
| GG5 | 增加聊天设置 UI 与前端状态同步 | Done | Node 检查、桌面与 390px Playwright 验证通过 |
| GG6 | 部署并完成线上健康、隔离、UI 与清理验收 | Done | 服务/Nginx active，内外 health OK，`CONTENT_MODE=local_only`，DB quick_check=ok |

## 验收记录

- 本地：`py_compile` 和 `node --check` 全部通过。
- 本地：`verify_galgame_conversation_option_local.py` 验证迁移、所有权隔离、复制、群聊不受影响、关闭恢复原状态、开启仅注入一次。
- 本地：`verify_galgame_conversation_api_local.py` 验证消息状态、切换 API、严格 boolean、跨用户 404 和列表持久化。
- 线上：真实活动全局预设运行块从 28 增至 29；目标条目开启前 0 次、开启后 1 次，位置 `post_history`、角色 `user`；全局预设 JSON 和 `api_settings.updated_at` 均未改变。
- 线上浏览器：刷新后按钮仍为 `is-active`；390×844 设置面板无横向/纵向溢出，console error 为 0。截图：`output/playwright/galgame-option-desktop-live.png`、`galgame-option-active-desktop-live.png`、`galgame-option-mobile-390-live.png`。
- 部署备份：`/opt/ai-fengyue-backend/backups/galgame-option-20260713-150900`，备份数据库 `quick_check=ok`。
- 清理：临时用户为 0，线上数据库 `quick_check=ok`。
