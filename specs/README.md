# Specs 导航

本目录保存可执行 SPEC 与历史交付记录。文件数量较多不会进入生产部署，但直接全目录浏览会产生导航噪声；后续开发优先从本页和项目 `AGENTS.md` 进入，不要默认通读全部历史文档。

## 当前主要入口

- Android PR #5 与 1.15.0 应用内更新：`homer-apk-update-20260905-tasks.md`（通知接口、更新入口、安装校验与系统安装器验收；原生源码在 `E:\homer-android`）

- 首屏本地壳接管与 1.14.1 (266) 上线：`homer-native-shell-handover-20260901-tasks.md`（覆盖更新包增量合并、WebView Java 桥 receiver bug、七场景实机验收）
- 交接 ZIP 合并与 1.14.0 (265) 上线：`homer-zip-merge-20260831-tasks.md`（三方合并方法、从 ZIP 改回的 9 处、新增 6 个验证工具）
- 生产数据本地备份：`homer-production-backup-20260824-requirements.md`、`homer-production-backup-20260824-design.md`、`homer-production-backup-20260824-tasks.md`
- 对话与模型选择生产恢复：`homer-chat-model-recovery-20260820-requirements.md`、`homer-chat-model-recovery-20260820-design.md`、`homer-chat-model-recovery-20260820-tasks.md`
- 新服务器迁移与部署：`homer-server-migration-20260818-requirements.md`、`homer-server-migration-20260818-design.md`、`homer-server-migration-20260818-tasks.md`
- 惑梦消息头与统一流式输出：`homer-message-header-streaming-20260812-requirements.md`、`homer-message-header-streaming-20260812-design.md`、`homer-message-header-streaming-20260812-tasks.md`
- 惑梦网页端 APK 壳：`homer-web-apk-20260812-requirements.md`、`homer-web-apk-20260812-design.md`、`homer-web-apk-20260812-tasks.md`
- 惑梦对话消息长按菜单：`homer-dialogue-message-menu-20260809-requirements.md`、`homer-dialogue-message-menu-20260809-design.md`、`homer-dialogue-message-menu-20260809-tasks.md`
- 《道渊》提示词助手与消息头像：`homer-daoyuan-prompt-helper-20260808-requirements.md`、`homer-daoyuan-prompt-helper-20260808-design.md`、`homer-daoyuan-prompt-helper-20260808-tasks.md`
- 惑梦对话预设可见性与操作收敛：`homer-dialogue-preset-controls-20260808-requirements.md`、`homer-dialogue-preset-controls-20260808-design.md`、`homer-dialogue-preset-controls-20260808-tasks.md`
- 惑梦反扒卡分享包与 APK 构建：`homer-share-and-apk-20260806-requirements.md`、`homer-share-and-apk-20260806-design.md`、`homer-share-and-apk-20260806-tasks.md`
- 惑梦原版 SillyTavern APK 打包前主线：`homer-sillytavern-apk-readiness-20260729-requirements.md`、`homer-sillytavern-apk-readiness-20260729-design.md`、`homer-sillytavern-apk-readiness-20260729-tasks.md`
- Web 聊天与长期能力：`web-chat-requirements.md`、`web-chat-design.md`、`web-chat-tasks.md`
- SillyTavern/Tavo 兼容：`sillytavern-parity-requirements.md`、`sillytavern-parity-design.md`、`sillytavern-parity-tasks.md`
- Web 产品壳与页面：`riliai-parity-requirements.md`、`riliai-parity-design.md`、`riliai-parity-tasks.md`
- 积分、充值和兑换：`credits-redemption-requirements.md`、`credits-redemption-design.md`、`credits-redemption-tasks.md`
- 完整角色资源包：`card-resource-pack-import-20260718-requirements.md`、`card-resource-pack-import-20260718-design.md`、`card-resource-pack-import-20260718-tasks.md`
- Spine/卡内发送桥：`spine-card-runtime-20260718-requirements.md`、`spine-card-runtime-20260718-design.md`、`spine-card-runtime-20260718-tasks.md`
- 社区工坊/不可变版本/Spine 稳定化：`community-version-spine-20260720-requirements.md`、`community-version-spine-20260720-design.md`、`community-version-spine-20260720-tasks.md`
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

- `community-version-spine-20260720-tasks.md`：新交接 ZIP 已提供 4.2 Spine 样本、社区和版本草案，当前按安全审计结果重构并验收。
- `tavo-worldbook-full-tasks.md`：本机未跟踪的待续草案，确认范围后再决定是否纳入 Git。
