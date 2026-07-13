# 惑梦 ZPAY 自动充值 Tasks

Updated: 2026-07-13

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| ZP1 | 读取官方文档并确认协议 | Done | submit/mapi、GET notify、MD5、success、重试规则已核对 |
| ZP2 | 建立 Requirements/Design/Tasks | Done | 本组 SPEC |
| ZP3 | 实现 payment_orders 与后端 API | Done | `py_compile` 通过；订单创建/查询、notify/return 与原子入账链路已实现 |
| ZP4 | 改造 Rewards/Me/Dashboard 主入口 | Done | 相关 JS `node --check` 通过；桌面与 390px 移动端实页无横向溢出和 Console Error |
| ZP5 | 本地安全与幂等测试 | Done | 首次回调入账、重复回调不重复入账、错签拒绝、return 不入账、用户隔离、旧直充默认 403 全部通过 |
| ZP6 | 备份、配置、部署线上 | Done | DB 在线备份 `quick_check=ok`；backend/env/frontend 均有时间戳备份；service/nginx active |
| ZP7 | 线上订单和官方收银台验证 | Done | 临时 ¥10 pending 订单被 ZPAY 正式网关接受并 302 到官方收银台；未付款余额不变，测试订单已清理 |
| ZP8 | 真实支付到账验证 | Pending | 等待一笔真实付款后核对 notify 与余额 |
| ZP9 | 更新记录并提交推送 | Done | 支付实现提交 `55fb9c0` 已推送到 `origin/main`；项目规则和 current-state 已更新 |

## 2026-07-13 验证记录

- 线上 `/console/api/web/deposit-meta`：`mode=zpay_direct`、`payment_provider=zpay`、`payment_available=true`，爱发电购买链接为空。
- 当前线上仅启用 `alipay`；前端支付方式完全以服务端公开配置为准。
- ZPAY 商户号和密钥只保存在服务器环境变量中，未写入仓库、浏览器响应、支付 URL、截图或验证报告。
- 旧爱发电兑换码库存与兑换历史保留，作为客服/回滚备用入口，不再作为用户主购买流程。
- ZP8 不能用模拟回调替代：必须由用户真实完成一笔付款，再核对 ZPAY notify、订单 `paid` 状态和 `paid_points` 只增加一次。
