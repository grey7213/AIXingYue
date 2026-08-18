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
- [x] `/app/open-source.html`、`/download/ai-xingyue-latest.apk` 返回 404；服务器 APK SHA-256 为 `c4639032e8ab799a157dd93b82b247c536d59f8431204e86264b41514faf803b`。
- [x] SQLite `quick_check=ok`；新库仅保留初始化管理员，不导入测试角色/离线数据库。
- [x] Chromium 桌面/390px 登录页截图和溢出检查通过，console/page error 为 0；仅有 Tailwind 浏览器运行时提示和 autocomplete 建议 warning。
- [x] CPA/Grok/Sub2API Docker 容器保持 healthy，相关 Nginx site symlink 未被替换。

## 待用户决定

- [ ] 提供正式管理员登录凭据或授权一次性管理员 API 验证；当前不在回复中猜测默认密码。
- [ ] 如需开放邮箱注册，提供新的 Resend/SMTP 凭据后单独配置并验收。
- [ ] 如需恢复角色卡/媒体库，提供正式生产备份；当前 ZIP 不含可投产数据库/媒体库。
- [ ] 如需公开 APK 下载，明确授权后再将 `APK_DOWNLOAD_ENABLED` 和 Nginx 下载路由按安全方案开启。
