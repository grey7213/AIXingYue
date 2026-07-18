# Specs 导航

本目录保存可执行 SPEC 与历史交付记录。文件数量较多不会进入生产部署，但直接全目录浏览会产生导航噪声；后续开发优先从本页和项目 `AGENTS.md` 进入，不要默认通读全部历史文档。

## 当前主要入口

- Web 聊天与长期能力：`web-chat-requirements.md`、`web-chat-design.md`、`web-chat-tasks.md`
- SillyTavern/Tavo 兼容：`sillytavern-parity-requirements.md`、`sillytavern-parity-design.md`、`sillytavern-parity-tasks.md`
- Web 产品壳与页面：`riliai-parity-requirements.md`、`riliai-parity-design.md`、`riliai-parity-tasks.md`
- 积分、充值和兑换：`credits-redemption-requirements.md`、`credits-redemption-design.md`、`credits-redemption-tasks.md`
- 完整角色资源包：`card-resource-pack-import-20260718-requirements.md`、`card-resource-pack-import-20260718-design.md`、`card-resource-pack-import-20260718-tasks.md`
- Spine/卡内发送桥：`spine-card-runtime-20260718-requirements.md`、`spine-card-runtime-20260718-design.md`、`spine-card-runtime-20260718-tasks.md`
- APK/早期逆向主线：`requirements.md`、`design.md`、`tasks.md`、`zip-1-repack-*`

## 运维 Runbook

- `aifadian-redeem-runbook.md`
- `email-smtp-resend-runbook.md`
- `production-launch-security-review.md`

## 历史文档规则

- 其余按功能或日期命名的 requirements/design/tasks 是已完成交付的历史证据，默认只在排查回归、追溯设计决定或继续对应功能时读取。
- 已完成文档暂不大规模移动，避免破坏 `AGENTS.md`、脚本、Skill current-state 和旧提交中的路径引用。
- 新功能继续使用独立的 requirements/design/tasks；完成后在 tasks 中写入真实验证结果，并把本页“当前主要入口”更新为仍在维护的主线。
- 截图、trace、临时验证脚本继续放在 `output/`。根目录不得放一次性截图。

## 当前未完成事项

- `spine-card-runtime-20260718-tasks.md`：等待实际 Spine 导出包和明确版本后完成资源组导入与合法运行时接入。
- `tavo-worldbook-full-tasks.md`：本机未跟踪的待续草案，确认范围后再决定是否纳入 Git。
