# 惑梦（Homer）新服务器迁移设计

## 部署拓扑

```text
Internet
  └─ Nginx :80/:443 (patcher.villainy.top)
       ├─ static /var/www/ai-fengyue-frontend
       ├─ backend routes → 127.0.0.1:8008
       └─ /module/dialogue/ → 127.0.0.1:8091
```

后端和 dialogue 分别使用 `ai-xingyue`、`homer-dialogue` 专用账户；runtime 源码按时间戳发布到 `/opt/homer-dialogue-runtime/releases/<stamp>`，`current` 以 symlink 原子切换，运行数据固定在 `/var/lib/homer-dialogue`。

## 迁移顺序

1. 校验 ZIP/APK 哈希，解包到 ASCII staging 路径并执行 Python/Node 静态预检。
2. 备份新机 Nginx、证书、站点、systemd 和 `/var/www`；只对目标站点写配置。
3. 检查证书依赖。若 `/etc/letsencrypt/ssl-dhparams.pem` 缺失，先生成 2048-bit DH 参数并通过 `nginx -t`。
4. 备份现有 SQLite（若有）后上传后端模块、生成安全 env、初始化/保留数据库。
5. 打包上传 dialogue/frontend，远端以 SHA-256 校验；dialogue 使用 `npm ci --omit=dev` 并锁定 webpack `5.105.4`。
6. 原子切换 runtime、启动 backend/dialogue，生成 patcher Nginx 站点并 reload。
7. 执行内部、公网、静态资源、404、TLS、SQLite、服务监听和浏览器验收。

## 回滚边界

- 部署器失败时只恢复 dialogue `current`/unit 和目标 patcher 站点，不触碰其他 Nginx site、Docker 或业务备份。
- 前端源码归档和 SQLite 备份保留在 backend `backups/`，由部署器管理保留策略。
- 已成功验收的部署不因备份裁剪告警回滚。

## 当前产品开关

新机 env 保持 `CONTENT_MODE=local_only`、`USER_BYOK_ENABLED=false`、`PAYMENT_CHANNEL_ENABLED=false`、`CTF_DIRECT_RECHARGE_ENABLED=false`、`APK_DOWNLOAD_ENABLED=false`、`ALLOW_EMAIL_SEND_FAILURE=false`、`ALLOW_ANY_REGISTER_CODE=false`、`AUTH_COOKIE_SECURE=true`。邮件/支付凭据需用户后续明确提供，不能从测试包推断。
