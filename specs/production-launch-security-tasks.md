# 惑梦正式上线安全任务

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| PLS1 | 建立正式上线安全 SPEC 与现状审计 | Done | 后端、前端、支付和线上基础设施并行审查，见 `production-launch-security-review.md` |
| PLS2 | 开放注册总量并降低注册送额度至 500 | Done | 线上临时账号初始 500；env `BETA_MAX_REGISTERED_USERS=0` |
| PLS3 | 签名并过期登录 token，移除默认用户回退 | Done | 旧/篡改 token 失败；无 token profile/credits/orders/chat/admin 为真实 HTTP 401；旧 token 浏览器自动清理并回到登录页 |
| PLS4 | 阻断用户 Base URL 窃取站点模型 Key/SSRF | Done | 用户创建卡提交攻击者 URL 后响应和 DB 均为空；站点模型地址只取管理员预设 |
| PLS5 | 加固登录、请求体、图片代理和 CORS | Done | PBKDF2、登录/验证码限流、32MB body、10MB 图片代理、禁重定向、恶意 Origin 无 ACAO、日志递归脱敏 |
| PLS6 | 部署、线上 API 与浏览器验证 | Done | backend/Nginx active，内外 health OK，local_only；桌面 1440 和移动 390 无溢出/console error；临时用户、订单和验证码已清理 |
| PLS7 | 提交、推送并形成剩余风险清单 | Done | 安全报告已形成；提交 `578aeb7` 已推送到 `origin/main` |

## 线上验收摘要

- 备份：`/opt/ai-fengyue-backend/security-backups/20260713-194207`，主库和邮件库 `quick_check=ok`，目录 `root:root 700`。
- 服务：后端以 `ai-xingyue` 低权限用户运行，`NoNewPrivileges=yes`、`ProtectSystem=strict`、`PrivateTmp/PrivateDevices=yes`；DB 600、env 640。
- SSH：密钥登录复验成功；密码登录、键盘交互和 X11 转发已关闭，root 仅允许密钥。
- Web：17 个页面不再执行外部 Tailwind CDN，改为本站固定 SHA-256 `176e894661aa9cdc9a5cba6c720044cbbf7b8bd80d1c9a142a7c24b1b6c50d15`；HSTS/CSP/XFO/nosniff/Referrer/Permissions 头已上线。
- 支付：ZPAY 与爱发电并存，默认支付宝，自定义金额和订单列表正常；客户端伪造 points 不生效，未执行真实付款。
