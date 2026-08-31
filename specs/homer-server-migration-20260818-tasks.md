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
- [x] 正式发布 APK（2026-08-25 完成）：原发布 keystore 并未丢失，是 `output/zip-1-repack/zip1-repack.keystore`（被 `.gitignore` 挡住所以先前误判为不存在）。五个历史公开包证书指纹全为 `429b…f320`，与该 keystore 一致。已用 `assembleRelease` + zipalign + apksigner(v2/v3) 出 `homer-1.13.0-262-release-signed.apk`（42,095 bytes，sha256 `e9e25c3f…47bf2`，包名 `org.nebula.horizon.composeai`，262/1.13.0），并已发布为 canonical。
- [x] 已按用户要求公开 APK 下载；`APK_DOWNLOAD_ENABLED=true`，Nginx 下载路由、Content-Type、Content-Disposition、checksum 与 `release.json` 已验证。**2026-08-25 更正**：08-20 的角色卡恢复部署把 Nginx 重写回了 `/download/ → 404`，公开下载实际中断了 5 天；已修 `deploy_ai_fengyue_villainy.py` 让该路由跟随 `APK_DOWNLOAD_ENABLED`，canonical 也已从 debug 体验包换成正式签名包。

## 2026-08-25 补记（APK 正式化与两处部署回退修复）

- [x] 覆盖安装实测：模拟器先装已发布的 261（`homer-web-apk-signed.apk`），再不卸载直接装 262，`Success`；`firstInstallTime` 保留、`lastUpdateTime` 更新，确认为原地升级而非重装。
- [x] 从公网 URL 下载后再装一遍：下载物 sha256 与本地构建一致，覆盖 261 装成 262 成功。
- [x] 冷启动实测：前台为 `HomerActivity`，加载线上 `/app/login.html`（服务器 access log 记到 UA `HomerAndroid/1.13.0`），logcat 无 FATAL。
- [x] 静态审计：17 个 ZIP 条目、单个 `classes.dex`、无 `lib/`；dex 内只有 `https://patcher.villainy.top/` 与 `/app/` 两个 URL；旧/新服务器 IP、CelestiAI、`sk-` key、Resend/ZPAY/SMTP、ADMIN_EMAILS、私钥头、旧品牌命中均为 0。Manifest 无 `debuggable`，`allowBackup=false`、`usesCleartextTraffic=false`。
- [x] 单元测试 `clean test`：debug/release 各 10 个（PatchSlotState 3 / PatchVerifier 3 / SafeUrls 4），0 failure 0 error。
- [x] Nginx `/download/` 路由恢复并落进部署模板（`env_flag_enabled()` + `download_locations()`），生成结果与线上 diff 只差目标那一段，`nginx -t` 通过。
- [x] 首页/dashboard 下载文案与事实改回开放态，`download_facts` 从错的「v1.0.0 / Android 5.0+ / ARM,ARM64」改成「v1.13.0 / Android 8.0+ / 全机型通用」；1440 与 390px 真实浏览器验证 0 console/page error、无横向溢出。
- [x] `homer-dialogue` hostWhitelist 恢复，并把根因修在仓库 `sillytavern-runtime/config.yaml`（部署会直接打包它）。Host 探测：白名单内 302，`evil.example.com`/`villainy.top` 403。IP 字面量放行是 `host-validation-middleware` 的设计（只防 DNS rebinding），非配置问题。
- [ ] APK 内登录后的真实对话验收：缺可用测试账号；未猜测生产密码，也未注册测试账号污染生产库。
- [ ] `zip1-repack.keystore` 离线备份：全盘只有一份且不在 `E:\homer-backups\` 里，磁盘损坏即永久失去签名身份。
- [ ] 旧 debug 体验包（`homer-android-1.13.0-{app-,local-,}debug.apk`）仍留在 `/download/`；它们是 `.debug` 包名，装了会并存出第二个应用。待确认后用 `publish_homer_apk.py --prune-debug` 下架。
- [ ] 生产后端跑的是未提交代码：`/opt/ai-fengyue-backend/ai_fengyue_local_server.py` 与工作区文件逐字节一致，含约 217 行未提交的 SillyTavern bridge 改动（08-20 上线）。需要补提交，否则无法从 git 复现或回滚。

