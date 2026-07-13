# 惑梦正式上线安全审查报告

日期：2026-07-13

## 已修复的上线阻断项

- 身份令牌：旧两段式 token 无签名、无过期，可伪造用户甚至管理员。现改为 `local.<payload>.<HMAC-SHA256>`，含 `sub/iat/exp/scope`，默认 30 天；旧、篡改和过期 token 均拒绝。
- 匿名默认账户：私有接口不再回退默认用户，无 token 的资料、余额、订单、兑换、聊天、会话和后台接口返回真实 HTTP 401。
- 私有角色泄露：匿名角色详情只允许 `is_public=1` 且 `status=published`；私有、草稿和下架卡统一 404，收藏/聊天记录子路径不再误入详情白名单。
- 模型密钥与 SSRF：普通用户角色不保存 `api_base_url`，站点 API Key 只会发往管理员配置的模型预设地址。
- 密码与登录：新密码使用随机盐 PBKDF2-SHA256 260000 次；旧 SHA256 登录后自动升级；密码最低 8 位；登录按邮箱/IP 限制失败次数。
- 验证码：独立邮件库增加邮箱/IP 小时限额、60 秒冷却、单码最多 5 次错误尝试和常量时间比较。
- 日志：Authorization、Cookie、密码、验证码、token、key、secret 递归脱敏；旧 `request_log` 已在安全备份后清空。
- 网络与资源：正式域同源 CORS、32MB 请求体限制、图片代理 HTTPS 域名白名单、禁重定向、image Content-Type 和 10MB 上限。
- 前端：移除外部 Tailwind CDN，修复运营导航 DOM XSS、登录开放重定向、聊天背景 CSS 注入；旧 token 会自动清理并引导重新登录。
- 基础设施：后端从 root 迁移到专用用户并启用 systemd 沙箱；DB/env 权限收紧；SSH 密码登录关闭；全站上线安全响应头。

## 支付审查

- ZPAY notify 会校验签名、PID、订单号、服务端金额、支付类型和 `TRADE_SUCCESS`。
- 入账在 SQLite 写事务中完成，订单状态原子从 pending 更新到 paid，provider trade number 唯一，重复通知不重复加币。
- return 页面只跳转和查状态，不入账；订单查询按 token 用户隔离。
- 爱发电卡密兑换保留；在线支付宝支持固定套餐和服务端计价的 `1.00–5000.00 CNY` 自定义金额。
- 本轮只做非金融回归，没有伪造支付回调或执行真实付款；最终财务验收仍需一笔真实小额支付。

## 已验证结果

- 新注册账号 `500` 惑梦币，注册总量上限 `0`，已有账号余额不变。
- 旧/篡改 token 401；匿名私有接口 401；私有卡匿名 404、本人 200。
- 用户提交攻击者 Base URL 后响应和数据库均为空。
- PBKDF2、恶意 Origin 无 ACAO、日志敏感哨兵不落库、安全响应头均通过。
- 线上桌面 1440 与移动 390 充值页显示爱发电、在线支付宝、自定义金额和支付订单，无横向溢出和 console error。
- backend/Nginx active，内外 `/health` OK，`CONTENT_MODE=local_only`，数据库 `quick_check=ok`。

## 上线后仍需安排

- 系统有 `115` 个待更新包且标记需要重启。应安排维护窗口先做快照/备份，再升级、重启并回归服务。
- 公网 `8080` 仍由另一 Villain Y 服务监听，本轮未关闭以免误伤其他项目；确认用途后再决定防火墙收口。
- CSP 仍包含 `unsafe-inline`/`unsafe-eval`，原因是现有 Alpine 与浏览器版 Tailwind 运行时。下一阶段应编译静态 CSS、移除内联表达式后收紧 CSP。
- Bearer token 仍保存在 localStorage。当前通过短期签名、过期和 XSS/第三方脚本收口降低风险；长期应迁移为 HttpOnly Secure SameSite 会话并支持服务端撤销。
- `protected_prompt=true` 的公开角色详情仍可能返回完整提示词/世界书；如该标记用于防导出，应设计公开详情脱敏字段，而聊天运行时继续读取服务端完整数据。
- 当前备份是同机 root-only 安全快照；正式运营应增加加密异机备份、恢复演练和保留策略。
- 建议补 fail2ban/等效 SSH 暴力破解封禁、监控告警、依赖漏洞扫描和定期权限审计。
