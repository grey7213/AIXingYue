# 惑梦农场技术设计

## 页面与导航

- 新页面：`frontend/app/farm.html`。
- 独立样式与逻辑：`frontend/app/assets/css/farm.css`、`frontend/app/assets/js/farm.js`，避免覆盖现有 `app.css` 用户改动。
- 复用现有 App Shell、Bearer token、Toast 语义和登录跳转。
- `rewards.html` 保留充值、订单、爱发电和兑换码，只把每日签到卡改为农场入口。
- `me.html`、`dashboard.html` 的直接签到按钮改为跳转农场；`layout.js` 的“每日奖励”导航改为“农场”。

## 数据结构

### `farm_profiles`

- `user_id` 主键。
- `coins`：农场币，默认 300。
- `xp`：经验，默认 0。
- `energy`：已结算体力，默认 5，上限 5。
- `energy_updated_at`：体力结算时间。
- `streak_days`：连续活跃天数。
- `last_active_date`：最近活跃业务日期。
- `harvest_count`：累计收获。
- `created_at`、`updated_at`。

### `farm_plots`

- 复合主键 `(user_id, plot_no)`，`plot_no` 1-8。
- `crop_kind`、`planted_at`、`ready_at`、`watered_at`。
- 空地以 `crop_kind` 为空表示；锁定状态根据 `streak_days` 动态计算，不存客户端标记。

### `farm_actions`

- 复合唯一键 `(user_id, idempotency_key)`。
- 保存 `action_type`、`request_fingerprint`、`response_json`、`created_at`。
- 相同键且请求指纹一致时回放原结果；指纹不同则拒绝。

### `farm_steals`

- 保留历史兼容表，不删除既有记录。
- 2026-07-13 V2 起停止生成系统 NPC，真实好友关系未接入前不再新增采摘记录。

## 规则

- 北京时间自然日沿用 `business_date()`。
- 连续活跃：首次进入记 1 天；次日进入 +1；跨过一天则重置为 1。同一天重复进入不增加。
- 土地解锁阈值：第 1 块立即开放，其余分别为连续 7/14/21/28/35/42/49 天。
- 作物：
  - 代码胡萝卜：成本 50 农场币，3 小时，收获 90 农场币，10 XP。
  - 算力小麦：成本 100，9 小时，收获 190，22 XP。
  - 灵感莓果：成本 180，18 小时，收获 340，40 XP。
- 浇水：每株每次种植最多一次，消耗 1 体力，将剩余成熟时间减少 20%，至少保留 60 秒。
- 体力：上限 5，每 30 分钟恢复 1 点，服务端惰性结算。
- 收获：成熟后清空土地并发农场币/XP；再调用 `claim_daily_reward()` 尝试领取当日惑梦币。已由旧签到或其他收获领取时 `points_added=0`。
- 好友农场：当前返回真实好友功能准备中的空状态；不生成虚构好友，不发放 NPC 采摘奖励。

## API

- `GET /console/api/web/farm/state`
- `POST /console/api/web/farm/plots/{plot_no}/plant`，body `{crop_kind}`
- `POST /console/api/web/farm/plots/{plot_no}/water`
- `POST /console/api/web/farm/plots/{plot_no}/harvest`
- `GET /console/api/web/farm/friends`
- `POST /console/api/web/farm/friends/{friend_id}/steal`：兼容保留，真实好友未开放时返回 409。

动作接口读取 `Idempotency-Key`；响应均返回最新 `state` 或足够前端原子更新的数据。

## 事务与兼容

- 每个农场动作在 `Store.lock` 下用一个 SQLite 事务完成状态校验、扣费/奖励、动作账本和事件记录。
- 农场收获对惑梦币的发放继续落到 `daily_reward_claims`；旧签到接口不改响应字段。
- 用户会话、角色、支付和聊天表不迁移、不删除、不重写。

## 验证

- Python：语法编译、临时 SQLite 初始化、种植/浇水/成熟/收获、体力恢复、连续天数、好友空状态、旧 NPC 停用、幂等键冲突和同日奖励唯一性。
- JavaScript：`node --check`。
- 浏览器：真实本地服务登录后操作，桌面 1440px 与移动 390px 截图，检查溢出、弹窗、加载/错误/空状态。
- 线上：部署前备份 DB/backend/frontend；部署后检查 service、Nginx、`/health`、`CONTENT_MODE=local_only`，用临时用户完成农场 E2E 并清理。
