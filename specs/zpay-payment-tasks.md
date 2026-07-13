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
| ZP10 | 双通道与自定义金额需求/设计更新 | Done | Requirements/Design 增加爱发电并列入口、自定义金额服务端规则 |
| ZP11 | 后端支持自定义金额并同时公开爱发电 | Done | 12.34→12340；边界/小数/科学计数/伪造积分/固定套餐/幂等回归通过 |
| ZP12 | Rewards 双通道和自定义金额 UI | Done | 桌面/390px：两入口可见、12.34→预计 12340、0.99 提示、无溢出/console error |
| ZP13 | 备份部署与线上未付款验证 | Done | 备份 quick_check=ok；固定 ¥10/自定义 ¥12.34 均 302 到官方收银台、pending、余额不变、已清理 |
| ZP14 | 更新记录并提交推送（二次扩展） | Done | 实现提交 `d72d247` 已推送到 `origin/main`；current-state 与项目规则已更新 |

## 2026-07-13 验证记录

- 线上 `/console/api/web/deposit-meta`：`mode=zpay_direct`、`payment_provider=zpay`、`payment_available=true`，爱发电购买链接为空。
- 当前线上仅启用 `alipay`；前端支付方式完全以服务端公开配置为准。
- ZPAY 商户号和密钥只保存在服务器环境变量中，未写入仓库、浏览器响应、支付 URL、截图或验证报告。
- 旧爱发电兑换码库存与兑换历史保留，作为客服/回滚备用入口，不再作为用户主购买流程。
- ZP8 不能用模拟回调替代：必须由用户真实完成一笔付款，再核对 ZPAY notify、订单 `paid` 状态和 `paid_points` 只增加一次。

## 2026-07-13 双通道与自定义金额扩展

- 线上同时公开 `payment_providers=[zpay,aifadian]`；爱发电域名为 `ifdian.net`，在线支付类型为 `alipay`。
- 自定义金额范围 `1.00–5000.00`，`points_per_cny=1000`；`12.34` 元由服务端生成 `12340` 惑梦币订单。
- 固定套餐提交伪造的 `amount_cny/points/plan_name` 不影响服务端套餐快照；自定义订单伪造 `points/plan_name` 同样无效。
- 拒绝 `0.99`、`5000.01`、三位小数、科学计数、NaN 和空金额；固定套餐和原 notify 幂等安全回归通过。
- 线上备份：`/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-dual-payment-20260713-153847.sqlite3`，大小 `1458180096`，`quick_check=ok`。
- 固定 ¥10 与自定义 ¥12.34 未付款订单均被 ZPAY 接受并 302 到 `api.z-pay.cn`，订单保持 pending、用户余额不变，测试订单清理后 DB `quick_check=ok`。
