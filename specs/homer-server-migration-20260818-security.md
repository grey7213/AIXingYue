# 新服务器主机安全验收（2026-08-18）

新机默认 SSH 配置曾允许密码登录和 root 密码直登，且未安装 Fail2ban。完成项目部署后已先备份 `/etc/ssh/sshd_config`、`/etc/ssh/sshd_config.d` 和（若存在）`/etc/fail2ban` 到：

`/root/homer-ssh-pre-hardening-20260818170857`

随后完成：

- `/etc/ssh/sshd_config.d/00-homer-security.conf`：关闭密码/键盘交互登录、root 仅允许密钥、关闭 X11 转发。
- `sshd -t` 和 `sshd -T` 通过，现有密钥新连接验证为 `KEY_LOGIN_OK`。
- 安装并启用 Fail2ban，`sshd` jail active；验收时已有 2 个扫描源被封禁。
- backend、dialogue、Nginx 仍 active，8008 `/health` 返回 `OK`；Docker/CPA/Grok/Sub2API 未改配置。

回滚时先恢复上述备份中的 SSH 配置并 `sshd -t && systemctl reload ssh`；Fail2ban 配置位于 `/etc/fail2ban/jail.d/homer-sshd.local`。
