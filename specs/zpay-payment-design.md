# 惑梦 ZPAY 自动充值 Design

Updated: 2026-07-13

## 配置

- `ZPAY_ENABLED`
- `ZPAY_GATEWAY=https://zpayz.cn/`
- `ZPAY_PID`
- `ZPAY_KEY`
- `ZPAY_NOTIFY_URL=https://patcher.villainy.top/console/api/web/payments/zpay/notify`
- `ZPAY_RETURN_URL=https://patcher.villainy.top/console/api/web/payments/zpay/return`

## 数据库

`payment_orders`：

- `order_no text primary key`，本站最多 32 位订单号。
- `provider text`、`provider_trade_no text unique`。
- `user_id text`、`plan_id text`、`plan_name text`。
- `amount_cents integer`、`points integer`、`pay_type text`。
- `status text`：`pending|paid|refunded|closed|failed`。
- `created_at`、`paid_at`、`notified_at`、`updated_at`。
- `client_ip`、`provider_buyer`，不保存 PID/KEY 或完整敏感回调。

## API

- `POST /console/api/web/payments/orders`
  - Auth body: `{plan_id, pay_type}`。
  - 返回订单号、金额、积分、状态和签名后的 ZPAY `pay_url`。
- `GET /console/api/web/payments/orders/{order_no}`
  - 只返回当前用户自己的订单和最新余额。
- `GET /console/api/web/payments/zpay/notify`
  - 公共回调，验签、金额校验、幂等入账，成功返回纯 `success`。
- `GET /console/api/web/payments/zpay/return`
  - 验签后 302 返回 Rewards，并携带本站订单号；到账仍以 notify 为准。

## 前端

- Rewards 套餐按钮改为选择支付方式并调用创建订单接口。
- 前端只跳转后端返回且 host 为 `zpayz.cn` 的 HTTPS URL。
- return 回到 Rewards 后轮询订单状态，显示“等待支付 / 已到账 / 支付处理中”。
- 兑换码区域降级为“备用兑换码”，不再展示爱发电购买文案。

## 切换策略

1. 本地假 KEY 验证完整回调闭环。
2. 备份线上 DB、后端、前端和 env。
3. 部署代码但先验证配置完备。
4. 写入真实 ZPAY 环境变量并开启。
5. 创建未支付真实订单，确认 ZPAY 收银台参数正确。
6. 用户完成一笔真实小额/正式套餐支付后，确认 notify 自动到账，再正式认为支付闭环生产验证完成。
