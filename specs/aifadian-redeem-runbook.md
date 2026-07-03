# AI星月 爱发电卡密运营 Runbook

## 当前推荐方案

先使用“爱发电购买 -> 爱发电自动发货兑换码 -> 用户回 AI星月兑换”的卡密方案。

原因：

- 不需要立即接爱发电 OpenAPI、Webhook 或支付回调，稳定性最高。
- 现有 AI星月后端已经支持一次性兑换码、防重复核销、余额拆分和兑换记录。
- 用户无需在付款时暴露 AI星月账号；复制卡密到 `/app/rewards.html` 兑换即可。
- 后续即使接自动化，也可以复用同一套 `redeem_codes` 和 `redemption_history` 数据结构。

暂不建议一开始做“购买后直接绑定账号自动加积分”：

- 需要爱发电开放平台 `user_id/token`、订单查询或回调，并处理签名、重试、幂等、退款/撤销。
- 需要用户在爱发电备注 AI星月邮箱/UID，或者做 OAuth/绑定码流程，用户操作更复杂。
- 自动加积分一旦实现不严，重复回调、伪造订单、填错账号都会造成资金/积分损失。

## 线上购买入口

- AI星月购买按钮：`https://patcher.villainy.top/app/rewards.html`
- 爱发电购买页：`https://ifdian.net/a/villainy`
- 线上 `deposit-meta` 已配置：
  - `aifadian_url=https://ifdian.net/a/villainy`
  - `payment_available=true`

配置命令：

```powershell
D:\Anconda3\python.exe .\tools\aifadian_redeem_ops.py configure --purchase-url https://ifdian.net/a/villainy
```

## 爱发电商品档位

在爱发电里按下面档位创建商品/发电方案，商品说明写明“自动发货兑换码，回 AI星月积分充值页兑换”。

| 商品 | 价格 | 兑换额度 | 约可回复 |
|---|---:|---:|---:|
| AI星月轻量包 | 10 CNY | 10000 星月币 | 约 200 次 |
| AI星月常用包 | 20 CNY | 22000 星月币 | 约 440 次 |
| AI星月高频包 | 50 CNY | 57500 星月币 | 约 1150 次 |
| AI星月深度包 | 100 CNY | 120000 星月币 | 约 2400 次 |
| AI星月月卡 | 19.9 CNY | 22000 星月币/月 | 约 440 次 |
| AI星月标准会员 | 39.9 CNY | 50000 星月币/月 | 约 1000 次 |
| AI星月 Pro 会员 | 79.9 CNY | 110000 星月币/月 | 约 2200 次 |

订阅商品必须写清楚：

- 这是月度额度包，不是无限使用。
- 额度用完后可继续购买积分包。
- 每次成功角色回复消耗 50 星月币。

## 生成卡密库存

脚本路径：

```text
tools\aifadian_redeem_ops.py
```

生成某个档位：

```powershell
D:\Anconda3\python.exe .\tools\aifadian_redeem_ops.py generate --plan xy_20 --count 100
```

生成所有档位，每档 20 个：

```powershell
D:\Anconda3\python.exe .\tools\aifadian_redeem_ops.py generate --plan all --count 20
```

生成 90 天有效期卡密：

```powershell
D:\Anconda3\python.exe .\tools\aifadian_redeem_ops.py generate --plan sub_month_standard --count 100 --expires-days 90
```

输出目录：

```text
output\aifadian-codes\YYYYMMDD-HHMMSS\
```

每个档位会生成：

- `.csv`：带价格、额度、备注，适合库存管理。
- `.txt`：一行一个兑换码，适合复制到爱发电自动发货库存。
- `summary.json`：本次生成摘要。

## 当前库存批次

2026-06-28 已生成首批可用于爱发电自动发货的真实兑换码库存：

```text
E:\酒馆开发\output\aifadian-codes\20260628-001621\
```

该批次包含 7 个固定档位，每档 20 个码：

- `xy_10-AI星月轻量包-10元-10000星月币`
- `xy_20-AI星月常用包-20元-22000星月币`
- `xy_50-AI星月高频包-50元-57500星月币`
- `xy_100-AI星月深度包-100元-120000星月币`
- `sub_month_light-AI星月月卡-19.9元-22000星月币`
- `sub_month_standard-AI星月标准会员-39.9元-50000星月币`
- `sub_month_pro-AI星月 Pro 会员-79.9元-110000星月币`

总配置清单：

```text
E:\酒馆开发\output\aifadian-codes\20260628-001621\爱发电商品配置总表.md
```

验证结果：本地每个档位目录都包含 `管理库存.csv`、`卡密库存-一行一码.txt`、`自动发货完整文案.txt` 和 `商品说明.md`；远程 SQLite 中 7 个爱发电备注分组均为 `20` 个未使用、未禁用兑换码。

注意：这些是真实可兑换额度的卡密文件，不要上传公开仓库、不要发给无关人员。

## 爱发电自动发货文案

可以在商品发货内容里放：

```text
感谢购买 AI星月。

你的兑换码：
{这里放一条兑换码}

兑换方式：
1. 打开 https://patcher.villainy.top/app/rewards.html
2. 登录你的 AI星月账号
3. 在“兑换码”输入框粘贴兑换码
4. 点击“兑换额度”，到账后网页和 APK 共用

注意：
- 一个兑换码只能使用一次。
- 请勿公开转发兑换码。
- 如兑换失败，请带订单号联系站长。
```

## 后续自动绑定账号方案

等卡密流程稳定后，再做自动绑定更合适。推荐路线：

1. 在 AI星月生成“购买绑定码”，例如 `XYUID-xxxxxx`，绑定当前用户。
2. 用户在爱发电下单备注这个绑定码。
3. 后端定时脚本用爱发电 OpenAPI 拉订单。
4. 根据订单金额映射到档位，按订单号做幂等表，给绑定用户加 `paid_points`。
5. 处理异常订单、重复订单、退款和备注错误。

自动绑定需要新增：

- `aifadian_orders` 表，记录订单号、金额、状态、用户、积分、处理结果。
- `user_purchase_bind_codes` 表，记录绑定码和过期时间。
- 爱发电 API 凭据环境变量，不写入代码和文档。
- 定时任务或 systemd timer。

在没有稳定订单 API 凭据和退款处理策略前，不建议直接上线自动加积分。
