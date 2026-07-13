# 惑梦农场 V2 更新设计

## 压缩包结论

- 新包是上一版 React/localStorage 原型的“去虚构数据”更新：删除假好友、假等级/XP/排名/API 调用量等演示统计，新增无好友空状态。
- 压缩包仍没有真实 API，会把完整 API Key 和农场币写入 localStorage，不能直接部署。
- ZIP SHA-256 为 `8E16D14D89458E787DEB72938C7C250864B567AB978009BE3BE9C1012605326C`；包内 `SHA256SUMS.txt` 全部通过。

## 落地映射

- 保留现有 `farm.html`、`farm.css`、`farm.js`、App Shell、Bearer 鉴权和服务端 `farm_*` API。
- 好友区域改为“真实好友准备中”的空状态，不再展示系统 NPC。
- `/console/api/web/farm/friends` 返回 `mode=real_friends_pending` 和空列表；旧 NPC 采摘接口返回 409，不再发放农场币/XP。
- 保留真实服务端 XP、等级、每日首收、作物图鉴、倒计时和充值入口，这些不是原型中的虚构统计。
- 移植新版更完整的第 3 生长阶段像素图与轻量阶段动画。

## 保持不变的边界

- 后端 SQLite 是农场资产、体力、成熟时间、奖励和每日账本的唯一权威。
- 前端只能发送动作意图与 `Idempotency-Key`。
- 旧签到与首次有效收获继续共享 `daily_reward_claims`。
- 不迁移或删除现有 `farm_steals` 历史记录；只停止继续产生 NPC 采摘记录。
