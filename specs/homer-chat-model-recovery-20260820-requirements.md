# 惑梦对话与模型选择恢复需求（2026-08-20）

## 目标

- 恢复正式站角色对话：普通发送必须收到真实模型 SSE 增量并正常结束。
- 恢复右上角模型选择：管理员公开启用的模型可选，保存后当前会话立即生效，刷新后仍保持。
- 模型或上游失败时不留下空白 assistant 消息、不扣惑梦币，并向用户显示脱敏且可理解的错误。
- 保持当前 8,778 张官方角色卡、用户数据、支付、邮箱、APK、安全配置和 SillyTavern/Homer 功能不变。

## 验收标准

- 公开模型接口至少返回一个启用模型、唯一默认模型且不包含 API Key/Base URL 等敏感字段。
- 极简 `stream:true` 节点探测可区分可用/失败模型，输出仅含模型名、状态、耗时和是否收到正文/终止事件。
- 极简私有角色通过完整 `/module/dialogue/` 链路收到多个可见增量和正常结束，回复落库，单轮只扣一次费用。
- 切换到另一个已验证模型后，`#custom_model_id`、会话运行时状态和刷新后的模型均一致。
- 故意选择失败节点/模拟上游错误时，本轮临时 user/assistant 数据均清理、余额不变、页面无空白消息。
- 1440×900 与 390×844 浏览器无横向溢出，console/page error 为 0。
- `ai-fengyue-backend.service`、`homer-dialogue.service`、Nginx active；内外 health 正常；`CONTENT_MODE=local_only`；SQLite `quick_check=ok`。

## 非目标

- 不重导入角色库，不改写 `local_apps.id/display_id`，不回滚 8 月 18 日线上定制 runtime。
- 不重新开放普通用户 BYOK，不暴露模型密钥、提示词、请求正文或角色卡私有数据。
- 不重建 APK，除非 Web/服务器恢复后另有明确需求。

