# 惑梦（Homer）新服务器迁移任务记录

## 已完成（2026-08-18）

- [x] 校验 `AIXingYue-main.zip` SHA-256：`2B4038421FA7AD8FD95A526F350F762F09E53D34E07BBEE90DCC010FA39253E2`。
- [x] staging 后端 7 个 Python 模块 `py_compile`、前端 JS/MJS `node --check`、runtime webpack/lock 预检。
- [x] 新机迁移前 root-only 备份：`/root/homer-migration-backup-20260818140910`。
- [x] 签发 `patcher.villainy.top` Let’s Encrypt 证书（有效期至 2026-11-16）。
- [x] 发现并修复缺失 `/etc/letsencrypt/ssl-dhparams.pem`；备份目录：`/root/homer-nginx-pre-dh-20260818145418`。
- [x] 部署 backend、frontend、SillyTavern runtime 和 systemd/Nginx 配置到 `38.76.218.46`。
- [x] backend/dialogue/Nginx active；8008 `/health=OK`；dialogue 仅监听 `127.0.0.1:8091`；runtime webpack `5.105.4`。
- [x] 公网 `/health`、`/app/`、`/app/chat.html`、`/admin.html` 通过；`.mjs` 返回 `text/javascript`。
- [x] `/app/open-source.html` 返回 404；APK 下载路由按发布记录提供公开 debug 体验包。
- [x] SQLite `quick_check=ok`；新库仅保留初始化管理员，不导入测试角色/离线数据库。
- [x] Chromium 桌面/390px 登录页截图和溢出检查通过，console/page error 为 0；仅有 Tailwind 浏览器运行时提示和 autocomplete 建议 warning。
- [x] CPA/Grok/Sub2API Docker 容器保持 healthy，相关 Nginx site symlink 未被替换。

## 备份核验与 APK 发布（2026-08-19）

- [x] 核验 `AIXingYue-main.zip`（2026-08-18，SHA-256 `2B4038421FA7AD8FD95A526F350F762F09E53D34E07BBEE90DCC010FA39253E2`）及离线数据库，确认仅含开发/E2E 数据。
- [x] 核验 2026-08-01 Homer 交接包及 2026-07-31 开发交接包；均无可恢复的生产用户/订单数据库。
- [x] 核验角色卡归档（含 8,778 张官方卡）可用于内容重建，但不导入账号、积分或历史会话。
- [x] 新服务器 live DB 与部署前 SQLite 备份均 `quick_check=ok`，仅保留初始化管理员；未灌入测试库。
- [x] 旧记录中的 `45.207.192.148` SSH 连接复核为超时；未从旧主机取回任何数据。
- [x] 旧公开 APK 文件完成备份和校验；随后用干净 ASCII 构建目录重新生成正式域名 debug 体验包（`41,114` bytes），公网下载与本地 SHA-256 一致。
- [x] 干净目录 `E:\homer-apk-clean` 运行 `clean testDebugUnitTest --rerun-tasks`：3 个 JUnit 测试全部通过；`assembleDebug assembleRelease` 通过，debug APK v2 签名和 zipalign 通过，release unsigned 产物仅用于构建检查。
- [x] Pixel_6_API_33_FirstPremium 模拟器安装并启动 debug APK；WebView 通过线上 HTTPS 登录页登录，读取 20 个模型/默认模型，并用临时角色完成真实 CelestiAI SSE（`message_end=true`、增量回复成功），测试数据已清理。
- [x] APK 静态审计确认不含 CelestiAI 上游地址、旧服务器 IP、管理员/支付/邮件凭据或私钥；包名 `org.nebula.horizon.composeai.debug`、版本 `1.13.0-debug (262)`，主 Activity 可启动。
- [x] 邮箱注册配置：Resend 凭据已写入并完成 provider/domain 验证；真实收件箱投递仍待验收。
- [x] 在线支付配置：ZPAY 凭据已写入并完成非财务跳转验证；真实小额支付回调仍待验收。

## 邮箱与 ZPAY 配置（2026-08-19）

- [x] 在写入前创建 root-only env 备份：`/root/homer-pre-mail-zpay-20260818-182926/ai-fengyue.env`（权限 `600`）。
- [x] Resend API 凭据已写入服务器 env（不记录密钥）；Resend API 返回 `villainy.top` 为 `verified`，发件人使用 `noreply@villainy.top`，`ALLOW_EMAIL_SEND_FAILURE=false` 保持失败即拒绝。
- [ ] 邮箱真实投递验收：等待用户提供一个收件测试邮箱；未在未确认收件人的情况下发送外部测试邮件。
- [x] ZPAY 已开启并写入服务器 env（不记录 PID/Key）：HTTPS 网关 `zpayz.cn`、支付宝类型；`deposit-meta` 返回 `mode=zpay_direct`、在线支付可用、`1 CNY=1000` 惑梦币。
- [x] ZPAY 无副作用配置验收：签名长度 32、生成支付 URL 不包含商户 Key、网关返回 `302` 至官方 `api.z-pay.cn`；伪造签名通知被拒绝。
- [ ] ZPAY 最终财务验收：需要用户完成一笔真实小额支付，确认异步通知、订单状态和恰好一次积分入账；禁止伪造成功回调。
- [x] 正式模型出口：已写入 CelestiAI OpenAI-compatible preset；后台自动读取 `/models` 得到 20 个候选，真实 `stream:true` 探测 20/20 通过，仅保存可对话模型；公开模型接口不返回 API key。
- [x] runtime host allowlist 已开启，仅允许 `patcher.villainy.top`、`127.0.0.1`、`localhost`；修改前备份到 `/root/homer-dialogue-security-backup-20260818-195427`，重启后 `homer-dialogue.service` active 且 `NRestarts=0`。

## 待用户决定

- [x] 已用用户提供的管理员账号完成登录和管理员 API 验证；凭据不写入代码、APK、SPEC 或报告。
- [ ] 邮箱真实投递验收：需要用户提供一个可查看的测试收件箱；当前 provider/domain 已验证，失败即拒绝注册码发送。
- [ ] 如需恢复角色卡/媒体库，提供正式生产备份；当前 ZIP 不含可投产数据库/媒体库。
- [ ] ZPAY 最终财务验收：需要用户实际完成一笔小额支付，确认异步通知、订单状态和恰好一次积分入账；不能伪造回调。
- [ ] 正式发布 APK：当前公开包为 debug 签名体验包；需要原发布 keystore 才能生成可覆盖旧安装的正式包。
- [x] 已按用户要求公开 APK 下载；`APK_DOWNLOAD_ENABLED=true`，Nginx 下载路由、Content-Type、Content-Disposition、checksum 与 `release.json` 已验证。当前公开产物仍明确标注为 debug 体验包。
