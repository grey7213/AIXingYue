# 惑梦农场替换签到任务

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| FARM1 | 审计 `农场.zip` 与现有签到链路 | Done | ZIP 无恶意可执行内容；确认原型为 localStorage 演示，旧新签到共享 `daily_reward_claims` |
| FARM2 | 补齐需求与技术设计 | Done | `farm-reward-requirements.md`、`farm-reward-design.md`、本文件 |
| FARM3 | 新增服务端农场表、规则、事务和 API | Done | `farm-backend-verify.py`：表、种植/浇水/收获、体力、连续天数、NPC、幂等与 16 路并发全部通过 |
| FARM4 | 移植农场视觉并接入真实 API | Done | 本地及线上 Playwright 桌面/390px 无溢出、无 console error；正确发送 `code_carrot` 与 `Idempotency-Key` |
| FARM5 | 替换签到入口与后台运营文案 | Done | 导航同时保留“惑梦农场”和“充值兑换”；Rewards/我的/Dashboard/后台文案已替换 |
| FARM6 | 本地回归旧 APK 签到与每日唯一奖励 | Done | 首次收获 +10；旧 `dailyapppoints` 随后 `points_added=0`；并发每日奖励唯一 |
| FARM7 | 备份、部署和线上 E2E | Done | 备份 `/opt/ai-fengyue-backend/backups/farm-20260713-134305`；线上 API、浏览器、支付回归与清理通过 |
| FARM8 | 精确提交并推送 `origin/main` | Done | 仅包含农场、入口、文案、SPEC 与项目规则文件；已推送 `origin/main` |

## 实现记录

- 2026-07-13：采用用户提供的像素农场原型作为已批准的 manual design handoff；正式版删除 API Key 绑定和 localStorage 权威状态。
- 2026-07-13：确定农场币与惑梦币分离，每日首次有效收获最多发放后台 `daily_points`，历史签到与旧 APK 接口继续共享每日唯一账本。
- 2026-07-13：线上临时用户验证初始 `500` 惑梦币/`300` 农场币/8 块土地；种植幂等回放成功、冲突返回 409；强制成熟后收获 `points_added=10`、余额 `510`、农场币 `340`；随后旧签到接口 `points_added=0`。
- 2026-07-13：支付回归保持 `zpay + aifadian`，自定义在线支付宝金额仍启用；临时用户和农场数据清理为 0，SQLite `quick_check=ok`。
- 2026-07-13：线上 `ai-fengyue-backend.service`、`nginx` active，内外 `/health` 为 OK，`CONTENT_MODE=local_only`；桌面和 390px 截图为 `output/playwright/farm-live-desktop.png`、`farm-live-mobile.png`。
- 2026-07-13 V2：用户新版 ZIP 主要删除虚构好友和虚构统计。正式版停止系统 NPC 展示与奖励，好友接口返回真实好友准备中的空状态，旧采摘接口返回 409；保留服务端 XP/等级、作物图鉴、每日首收和全部支付链路。截图为 `output/playwright/farm-v2-live-desktop.png`、`farm-v2-live-mobile.png`。
