# 惑梦对话与模型选择恢复任务（2026-08-20）

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| HCM1 | 清理前轮临时账号、会话、token 与远端临时文件 | Done | 前缀用户/会话均为 0，SQLite `quick_check=ok` |
| HCM2 | 审计线上 release、Backend、Frontend 与 staging 哈希差异 | In progress | 待记录 |
| HCM3 | 安全探测 `/models` 和候选模型 `stream:true` | Pending | 待记录 |
| HCM4 | 极简私有角色复现完整 Homer 对话链路 | Pending | 待记录 |
| HCM5 | 修复模型选择持久化和失败空消息/扣费体验 | Pending | 待记录 |
| HCM6 | 备份、部署并做桌面/390px/服务/DB 验收 | Pending | 待记录 |
| HCM7 | 更新 AGENTS/current-state、Git 提交与推送 | Pending | 待记录 |

## 当前证据

- 桌面/390px 均能打开模型设置，20 个选项存在，`#custom_model_id` 为当前默认模型。
- 重型公开角色真实发送后，上游约 1 秒返回 HTTP 500；浏览器无 JS/page error，但最终 assistant 正文为空并显示“对话服务连接失败”。
- 本轮清理删除 2 个 `codex-browser-models-*` 临时账号；清理后临时用户/会话为 0，数据库完整。

