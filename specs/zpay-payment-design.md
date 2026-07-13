# 惑梦 ZPAY 自动充值 Design

Updated: 2026-07-13

## 配置

- `ZPAY_ENABLED`
- `ZPAY_GATEWAY=https://zpayz.cn/`
- `ZPAY_PID`
- `ZPAY_KEY`
- `ZPAY_NOTIFY_URL=https://patcher.villainy.top/console/api/web/payments/zpay/notify`
- `ZPAY_RETURN_URL=https://patcher.villainy.top/console/api/web/payments/zpay/return`
- `ZPAY_CUSTOM_MIN_CNY=1.00`
- `ZPAY_CUSTOM_MAX_CNY=5000.00`
- `ZPAY_CUSTOM_POINTS_PER_CNY=1000`

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
  - 固定套餐 body：`{plan_id, pay_type}`。
  - 自定义金额 body：`{amount_cny, pay_type}`；不能同时依赖客户端 points/plan_name。
  - 返回订单号、金额、积分、状态和签名后的 ZPAY `pay_url`。
- `GET /console/api/web/payments/orders/{order_no}`
  - 只返回当前用户自己的订单和最新余额。
- `GET /console/api/web/payments/zpay/notify`
  - 公共回调，验签、金额校验、幂等入账，成功返回纯 `success`。
- `GET /console/api/web/payments/zpay/return`
  - 验签后 302 返回 Rewards，并携带本站订单号；到账仍以 notify 为准。

## 前端

- Rewards 套餐按钮改为选择支付方式并调用创建订单接口。
- Rewards 同时显示“在线支付宝”和“爱发电卡密”两个正式入口。
- 自定义金额输入只做格式/范围提示和预计到账展示，最终金额/积分以创建订单响应为准。
- 前端只跳转后端返回且 host 为 `zpayz.cn` 的 HTTPS URL。
- return 回到 Rewards 后轮询订单状态，显示“等待支付 / 已到账 / 支付处理中”。
- 爱发电按钮打开公开 `aifadian_url`；兑换码区域保留并明确用于爱发电自动发货卡密。

## 自定义金额规则

- 使用 `Decimal` 解析字符串，拒绝科学计数、负数、超过两位小数、范围外金额和非有限值。
- 金额转换为整数分后再持久化和签名，避免浮点误差。
- 自定义订单的 `plan_id=custom`、`plan_kind=custom`，`product_name` 由服务端生成。
- 自定义积分为 `amount_cents * points_per_cny / 100`，当前汇率保证结果为整数；固定套餐继续保留原奖励积分。

## 切换策略

1. 本地假 KEY 验证完整回调闭环。
2. 备份线上 DB、后端、前端和 env。
3. 部署代码但先验证配置完备。
4. 写入真实 ZPAY 环境变量并开启。
5. 分别创建固定套餐和自定义金额未支付订单，确认 ZPAY 收银台参数正确。
6. 用户完成一笔真实小额/正式套餐支付后，确认 notify 自动到账，再正式认为支付闭环生产验证完成。
