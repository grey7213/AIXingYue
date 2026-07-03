# AI星月 Credits / 爱发电兑换码需求

## 目标

- 将当前单一 `points` 余额升级为类似 riliaichat 的 credits 机制，同时保留 AI星月现有配色、资源和本地后端。
- 暂不直接接支付宝/微信/USDT 支付网关；充值按钮跳转到站长配置的爱发电购买页。
- 用户在爱发电购买后，拿到兑换码回到 AI星月网页兑换额度。
- 管理员可在后台生成、查看、禁用兑换码，并可继续调整用户余额。

## 余额类型

- `free_points`：系统赠送额度，例如注册、签到、活动赠送。
- `paid_points`：充值兑换获得额度。
- `reward_points`：邀请、创作、Mod 收益等奖励额度。
- `points`：兼容旧 APK 和旧接口的总余额，等于三类余额之和，或在旧逻辑未拆分时作为总余额来源。

## 用户流程

- `/app/rewards.html` 展示三类余额、奖励说明、兑换入口。
- `/app/me.html` 和 `/dashboard.html` 的充值入口可以引导到爱发电购买和兑换码输入。
- 用户点击购买后打开 `AIFADIAN_URL`；如果未配置，则显示“联系站长获取兑换码”。
- 用户输入兑换码，后端校验未使用、未过期、未禁用后，把对应额度加到指定余额类型，记录到 `redemption_history`。

## 管理员流程

- `/admin.html` 增加兑换码管理 Tab。
- 管理员可生成兑换码：
  - 数量
  - 每个兑换码额度
  - 余额类型：paid/free/reward
  - 备注
  - 可选过期时间
- 管理员可查看兑换码状态：未使用、已使用、已禁用、已过期。
- 管理员可禁用未使用兑换码。

## 验收标准

- 后端新增 API 可生成兑换码、兑换兑换码、查看余额拆分、查看兑换历史。
- 普通用户不能调用管理员兑换码 API。
- 一个兑换码只能成功兑换一次。
- 兑换成功后用户总积分和三类余额都能正确返回。
- 新注册用户默认获得 `5000` 免费积分额度。
- 每次成功生成一条聊天回复消耗 `50` 积分；余额不足时拒绝生成并提示用户充值或领取奖励。
- 充值展示口径统一为 `1 CNY = 1000` 积分；`50` 积分对应 `0.05 CNY` 单次聊天售价。
- 推荐积分包：`10 CNY -> 10000`、`20 CNY -> 22000`、`50 CNY -> 57500`、`100 CNY -> 120000`。
- 推荐订阅展示为月度额度包，不承诺无限用：`19.9 CNY -> 22000`、`39.9 CNY -> 50000`、`79.9 CNY -> 110000`。
- 注册/发码必须有基础反薅限制：重复邮箱不可再次注册，同一 IP 短期发码和注册免费额度领取有频率限制。
- 页面保持 AI星月配色，但 Deposit/Rewards/Me 的布局和交互密度贴近 riliaichat 的产品式弹窗和卡片。

## 非目标

- 不直接接入爱发电 OpenAPI 或 webhook。
- 不处理真实支付回调。
- 不自动识别爱发电订单；兑换码由管理员手动生成并发给购买用户。
- 不实现真正自动续费订阅；订阅档位先作为爱发电/兑换码购买说明和后台运营配置。

## 2026-06-27 实施状态

- 已上线 `1 CNY = 1000` 积分口径，`50` 积分约等于 `1` 次角色回复。
- 已配置爱发电购买页：`https://ifdian.net/a/villainy`。
- 已上线积分包：`10 CNY -> 10000`、`20 CNY -> 22000`、`50 CNY -> 57500`、`100 CNY -> 120000`。
- 已上线订阅展示：`19.9 CNY -> 22000/月`、`39.9 CNY -> 50000/月`、`79.9 CNY -> 110000/月`；订阅只表示月度额度包，不承诺无限使用。
- 已新增爱发电卡密运营脚本：`tools\aifadian_redeem_ops.py`，支持写入购买链接、按档位批量生成兑换码、导出 CSV/TXT。
- 已新增 runbook：`specs\aifadian-redeem-runbook.md`，记录爱发电商品档位、自动发货文案、卡密库存命令和后续自动绑定账号方案。
- 已上线基础反薅：重复邮箱拒绝发码/注册；同邮箱每小时 3 次发码、同 IP 每小时 8 次发码；同 IP 每天最多 3 个新账号领取注册赠送额度。
- 已上线 Web Logo 替换：`logo-64/128/256/512`、favicon、apple touch icon、`default_avatar.png`、`avatar.webp`、`empty_view.webp`、`base_logo.webp` 均换成用户提供的黑白斜杠 Logo。
- 验证：`output\verify_billing_logo_browser.py` 线上浏览器验收通过，前台桌面/移动 Rewards 和后台运营配置均渲染新套餐/订阅，Logo/默认头像/空态图加载正常，无 console/page error。

## 2026-07-03 临时关闭状态

- 按用户要求暂时关闭 APK 下载渠道和充值/兑换渠道，保留已有余额、每日奖励、聊天扣费和管理员兑换码库存管理能力。
- 后端运行开关默认关闭：`PAYMENT_CHANNEL_ENABLED=0`、`APK_DOWNLOAD_ENABLED=0`。以后恢复渠道时可显式开启对应 env，再保留原有爱发电配置和兑换码流程。
- 用户侧 `/console/api/web/deposit-meta` 返回 `mode=closed`、`payment_available=false`、`redeem_available=false`、`packages=[]`、`subscriptions=[]`。
- 用户兑换码接口 `/console/api/web/redeem-code` 和 APK 注入充值接口 `/console/api/ctf/recharge` 在关闭状态返回包体 `code=403`、`message=充值通道暂时关闭`。
- Nginx `/download/` 已返回 404，公网 `https://patcher.villainy.top/download/ai-xingyue-latest.apk` 不再分发 APK。
- 前端 Rewards/Me/Dashboard 不再渲染购买按钮、兑换输入、套餐和订阅卡片；首页和信息中心改为引导 Web App。
- 线上验证：service/nginx active，`CONTENT_MODE=local_only`，公开 `/health` 200；浏览器 `output/verify_channels_closed_browser.py` 验证首页无 APK 链接、无在线充值文案，Rewards/Me/Dashboard 均为维护态且无 console/page error。
