# 惑梦农场 V2 更新任务

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| FV2-1 | 审计新版压缩包内容与完整性 | Done | 52 个 ZIP entry，无路径穿越；包内 SHA256 全通过；npm audit 0 已知漏洞 |
| FV2-2 | 对比当前农场并更新设计映射 | Done | 确认为去虚构好友/统计更新；不引入 API Key/localStorage 权威状态 |
| FV2-3 | 实现必要的前端/后端兼容更新 | Done | 好友空状态、NPC API 停用、第 3 生长阶段像素图与动画已实现 |
| FV2-4 | 本地及浏览器回归 | Done | Python/Node/农场事务与旧签到通过；桌面/390px 0 error、无横向溢出 |
| FV2-5 | 备份、部署、线上验收与清理 | Done | 备份、服务、支付回归、DB 检查和临时数据清理全部通过 |

## 验收记录

- 新包 SHA-256：`8E16D14D89458E787DEB72938C7C250864B567AB978009BE3BE9C1012605326C`；包内 40 项 SHA256 全部通过，无路径穿越，npm audit 0 known vulnerabilities。
- 本地 `farm-backend-verify.py`：种植、浇水、收获、体力、连续活跃、好友空状态、旧 NPC 停用、幂等与旧签到共享奖励全部通过。
- 线上 `/farm/friends`：`mode=real_friends_pending`、好友数 0、剩余采摘次数 0；旧 NPC 采摘返回 409，农场币/XP/体力不变。
- 线上种植/强制成熟/收获正常，首次收获领取每日奖励，随后旧 `dailyapppoints` 返回 0。
- 支付回归：`payment_providers=[zpay,aifadian]`，自定义在线支付宝金额仍启用。
- 浏览器：第 1/2/3 生长阶段各渲染 1 个，第 3 阶段不再提前显示成熟造型；NPC 卡片 0，好友空状态存在；390px `horizontalOverflow=false`，console error=0。
- 截图：`output/playwright/farm-v2-live-desktop.png`、`output/playwright/farm-v2-live-mobile.png`。
- 备份：`/opt/ai-fengyue-backend/backups/farm-v2-20260713-161745`，备份数据库和线上数据库均 `quick_check=ok`；临时用户清理为 0。
