# 单会话全局预设开关任务

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| GP1 | 建立需求、设计与任务 SPEC | Done | 本目录三份单会话全局预设 SPEC |
| GP2 | 增加会话字段、兼容迁移、读写和复制语义 | Done | 旧库默认开启、所有权隔离、复制继承、`updated_at` 不变、DB quick_check 通过 |
| GP3 | 增加所有权 API 与前端状态同步 | Done | 严格 boolean、跨用户 404、列表/消息刷新持久化、A/B 会话隔离通过 |
| GP4 | 覆盖所有单聊生成入口并保持群聊/角色能力不变 | Done | Prompt `28 -> 0`、全局 Regex 关闭、角色 Regex 保留、Galgame 恢复、群聊无覆盖 |
| GP5 | 部署并完成线上健康、隔离、UI 和清理验收 | Done | backend/Nginx active，内外 health OK，390px 3×2 无溢出，console error=0，临时数据清零 |
| GP6 | 更新项目记录、提交并推送 | Done | 本轮相关文件按项目备份策略提交并推送 `origin/main` |

## 当前约束

- 不修改 APK。
- 不恢复普通用户 BYOK。
- 不部署或提交工作区中无关的 `app.css`、`workshop.html`、Tavo 文件和截图改动。

## 验收记录

- 本地 `verify_local.py` 验证兼容迁移默认开启、跨用户隔离、A/B 会话隔离、复制继承、群聊不受影响、全局 Prompt/Regex 关闭、角色 Regex 保留、Galgame 优先级和 DB `quick_check=ok`。
- 本地真实 HTTP 验证默认值、严格 boolean、跨用户 404、列表/消息持久化和恢复开启。
- 原 Galgame、48 模型目录和酒馆模板本地回归通过。
- 线上真实活动预设：开启会话有 28 条全局 Prompt 消息，关闭会话为 0；全局 Regex runtime disabled；后台 Prompt/Regex JSON 和更新时间未改变。
- 线上 API 验证 A 关闭、B 保持开启、复制继承、Galgame 关闭期间不生效且恢复全局后重新生效；临时用户/会话清零。
- 线上 390×844 浏览器验证设置区 6 张卡、无页面/菜单横向溢出；关闭后显示粉色“已关闭预设”，刷新保持，切换 B 会话仍为默认开启；console error=0。
- 截图：`output/playwright/conversation-global-preset-mobile-default.png`、`conversation-global-preset-mobile-disabled.png`。
- 部署备份：`/opt/ai-fengyue-backend/backups/global-preset-20260715-011529`，备份/live DB `quick_check=ok`。
