# 惑梦正式上线安全设计

## 注册策略

- 代码默认与线上环境统一：`BETA_MAX_REGISTERED_USERS=0`、`NEW_USER_INITIAL_POINTS=500`。
- `0` 继续沿用现有语义：无限制；邮箱/IP 日限额和生成并发限制保持启用。

## 鉴权

- token 格式升级为 `local.<payload>.<signature>`。
- payload 包含 `sub`、`iat`、`exp`、`scope`；签名使用 `HMAC-SHA256(AUTH_TOKEN_SECRET)`。
- 使用 `hmac.compare_digest` 验签；缺失密钥时生产环境拒绝启动或拒绝签发。
- `authenticated_user()` 与 `authenticated_token_user()` 均只接受有效 token，不再返回默认用户。
- 旧两段式 token 不兼容，正式上线后用户需重新登录。

## 模型上游边界

- 普通用户角色创建/导入/更新时清空 `api_base_url`。
- 站点 LLM 请求的 Base URL、协议和 API Key只来源于启用的管理员预设。
- 用户 BYOK 继续关闭；旧角色中的用户 URL 不再覆盖站点预设。

## 防滥用与网络

- 保留注册邮箱/IP频率与同 IP 每日免费账号限制。
- 增加登录失败按 IP/邮箱的短窗口限制。
- Nginx 与应用层设置请求体上限；图片代理禁止自动重定向并限制响应字节数。
- CORS 仅允许 `https://patcher.villainy.top`，不再对私有 JSON API返回 `*`。

## 部署

- 先备份 DB、backend、env、Nginx 和相关前端。
- 生成新的高熵 `AUTH_TOKEN_SECRET` 只写入线上 env，不写代码、Git、日志或回复。
- 部署后创建临时用户验证注册、登录、token、余额和私有接口，完成后清理。
