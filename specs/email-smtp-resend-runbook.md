# AI星月 邮件验证码 / Resend 接入 Runbook

Updated: 2026-06-22

## 2026-08-19 当前状态覆盖

- 新服务器 `38.76.218.46` 已写入新的 Resend 凭据（密钥值不记录在文档中）。
- Resend API 已验证 `villainy.top` 状态为 `verified`；当前发件人配置为 `AI星月 <noreply@villainy.top>`。
- `ALLOW_EMAIL_SEND_FAILURE=false` 保持不变；后端、Nginx、dialogue 均 active。
- 需要指定一个测试收件箱完成真实验证码投递验收；未在未确认收件人的情况下发送测试邮件。

## 新服务器交接（2026-08-18）

- 当前服务器：`38.76.218.46`；旧服务器 `45.207.192.148` 已退役。
- 新机安全配置暂不启用 SMTP/Resend：`SMTP_HOST=`、`ALLOW_EMAIL_SEND_FAILURE=false`。
- 下方 Resend 配置和验证记录是历史操作参考；重新开放邮箱注册前必须提供新的凭据并先备份 `/opt/ai-fengyue-backend/ai-fengyue.env`，不得直接照旧密钥恢复。

## 当前状态

- 线上后端使用 Resend SMTP：
  - `SMTP_HOST=smtp.resend.com`
  - `SMTP_PORT=587`
  - `SMTP_USER=resend`
  - `SMTP_FROM="AI星月 <onboarding@resend.dev>"`
- `ALLOW_EMAIL_SEND_FAILURE=false`，发送失败会明确返回错误。
- Resend 测试发件人 `onboarding@resend.dev` 只能投递到 Resend 账号自己的测试邮箱 `yjy112508@gmail.com`。
- 服务器直连外部 MX 的 25 端口超时，不能依赖本机 Postfix/sendmail 给普通邮箱投递。

## Resend 域名状态

Resend 中已有域名：

```text
domain: villainy.top
status: failed
region: us-east-1
```

失败原因：DNS 记录未添加或未生效。

## 需要在阿里云 DNS 添加的记录

域名 NS 当前为阿里云：

```text
dns29.hichina.com
dns30.hichina.com
```

在阿里云 `villainy.top` 解析里添加：

| 类型 | 主机记录 | 记录值 | 优先级 |
|---|---|---|---|
| TXT | `resend._domainkey` | `p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDaIohKridotlWzUyKQ8J5GxiVmwOpzeNODIV+ALiV2Hyy7zePR4dYYh+LRdMk2gk5EROho5H6dL4/wqslEAshe80yJfPOCZvh98IvFwKlTVU8N32tU0lPIqpSVN/XR8vB0RHyD61rG0+hxLP79mNK/sVJQ5my0MZEJXTzUqZW2fQIDAQAB` | - |
| MX | `send` | `feedback-smtp.us-east-1.amazonses.com` | `10` |
| TXT | `send` | `v=spf1 include:amazonses.com ~all` | - |

TTL 使用默认/自动即可。

## DNS 验证命令

```powershell
nslookup -type=TXT resend._domainkey.villainy.top
nslookup -type=MX send.villainy.top
nslookup -type=TXT send.villainy.top
```

## DNS 生效后切换发件人

```powershell
ssh -i 'C:\Users\86180\.ssh\villainy_backup_ed25519' root@38.76.218.46 "cd /opt/ai-fengyue-backend && cp ai-fengyue.env ai-fengyue.env.bak-resend-domain-$(date +%Y%m%d-%H%M%S) && python3 - <<'PY'
from pathlib import Path
p=Path('ai-fengyue.env')
lines=p.read_text(encoding='utf-8', errors='replace').splitlines()
out=[]
for line in lines:
    if line.startswith('SMTP_FROM='):
        out.append('SMTP_FROM=\"AI星月 <noreply@villainy.top>\"')
    else:
        out.append(line)
p.write_text('\n'.join(out)+'\n', encoding='utf-8')
PY
systemctl restart ai-fengyue-backend.service"
```

## 功能验证

发测试验证码到普通邮箱：

```powershell
curl.exe -k -sS -H 'Content-Type: application/json' --data-raw '{"email":"你的邮箱","lang":"zh-Hans"}' https://patcher.villainy.top/console/api/register/email
```

服务验证：

```powershell
ssh -i 'C:\Users\86180\.ssh\villainy_backup_ed25519' root@38.76.218.46 "systemctl is-active ai-fengyue-backend.service nginx; curl -fsS http://127.0.0.1:8008/health"
curl.exe -k -sS https://patcher.villainy.top/health
```
