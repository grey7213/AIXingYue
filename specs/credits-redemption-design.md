# AI星月 Credits / 爱发电兑换码设计

## 数据库

### `users` 扩展

- 增加 `free_points integer default 0`
- 增加 `paid_points integer default 0`
- 增加 `reward_points integer default 0`
- 兼容旧字段 `points`：读取余额时将旧 `points` 拆分为 `free_points` 的初始来源；写入时同步总额到 `points`。

### `redeem_codes`

- `code text primary key`
- `points integer not null`
- `point_type text not null default 'paid'`
- `note text`
- `created_by text`
- `created_at integer`
- `expires_at integer`
- `disabled_at integer`
- `redeemed_by text`
- `redeemed_at integer`

### `redemption_history`

- `id text primary key`
- `code text`
- `user_id text`
- `points integer`
- `point_type text`
- `note text`
- `created_at integer`

## API

### 用户 API

- `GET /console/api/user/credits`
  - 返回 `free_points`、`paid_points`、`reward_points`、`points`、`aifadian_url`。
- `POST /console/api/web/redeem-code`
  - body: `{ "code": "..." }`
  - 成功后返回新的余额拆分。
- `GET /console/api/web/redemptions`
  - 当前用户兑换记录。
- `GET /console/api/web/deposit-meta`
  - 返回爱发电 URL、推荐套餐、兑换说明。

### 管理员 API

- `GET /admin/api/redeem-codes`
- `POST /admin/api/redeem-codes/create`
- `POST /admin/api/redeem-codes/{code}/disable`

## 前端

- `frontend/app/rewards.html`
  - 增加三类余额卡片、爱发电购买入口、兑换码输入、兑换历史。
- `frontend/app/me.html`
  - 充值卡改为“购买兑换码 + 兑换额度”，保留当前 AI星月视觉。
- `frontend/assets/js/admin-app.js`
  - 新增 `redeem` Tab，可生成/查看/禁用兑换码。
- `frontend/assets/js/api.js` 和 `frontend/app/assets/js/app-core.js`
  - 增加用户和管理员 redemption API。

## 配置

- 后端环境变量 `AIFADIAN_URL`：爱发电购买页。
- 如果为空，前端显示“暂未配置购买链接，请联系站长获取兑换码”。

## 验证

- `py_compile` 后端。
- 用管理员 token 创建一次性兑换码。
- 用普通用户兑换，确认只成功一次。
- 线上页面 HTTP 200，浏览器检查 Rewards/Me/Admin 页面无 JS 错误。
