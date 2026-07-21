# 惑梦开放式聊天扩展运行时任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| OCR1 | 建立 requirements/design/tasks SPEC | Done | 本组三个文件 |
| OCR2 | 扩展前后端 `card_experience.chat_shell` schema | Done | Node/Python schema 断言；15 项权限和源码上限通过 |
| OCR3 | 实现单会话全屏 Open Chat Runtime | Done | opaque-origin iframe、CSP、MessageChannel、ready/超时/崩溃回退通过 |
| OCR4 | 接入消息快照、流式 patch 和 Host intents | Done | 发送/续写/重生成/swipe/编辑/删除/回溯/loadOlder/TTS 浏览器夹具通过 |
| OCR5 | 聊天页增加 Open Shell/默认 UI 切换和安全退出 | Done | 1440×960 与 390×844 无溢出，右侧安全退出标签不遮顶部/输入按钮 |
| OCR6 | 增加酒馆助手/Slash Runner 常用 API 别名 | Done | `HomerChat/TavernHelper/SillyTavern.getContext/triggerSlash` 夹具通过 |
| OCR7 | 扩展安装包贡献接入统一运行时 | Done | `.tpg contributes.chatShells` 导入、启用、包内三类源码读取和权限拒绝测试通过 |
| OCR8 | 本地与线上回归、部署和记录 | Done | 生产 health/MIME/SHA/DB/Chromium 通过；`CONTENT_MODE=local_only` |

## 当前约束

- 保留工作区已有的回复清洗、模型节点和 Tavo 世界书改动。
- 不在 v1 中重新开放用户 BYOK。
- 不让卡片或普通扩展直接执行主页面同源 JavaScript。

## 2026-07-21 本地验证结果

- `node --check`：`chat.js`、`open-chat-runtime.mjs`、schema 全部通过。
- Python：后端与媒体扩展 `py_compile` 通过；schema 与 `.tpg chatShells` 测试通过。
- Chromium：发送、流式状态、续写、重生成、Swipe、编辑、删除、回溯、加载旧消息、TTS、Slash、退出与崩溃回退通过。
- 安全：iframe sandbox 仅 `allow-scripts`；父 DOM/localStorage 均不可读；伪造 channel 不生效；桌面/移动端横向溢出均为 0。

## 2026-07-21 生产部署结果

- SQLite 在线备份：`/opt/ai-fengyue-backend/backups/ai_fengyue-before-community-versions-20260721-160127.sqlite3`，live/backup `quick_check=ok`。
- 定向源码备份：`/opt/ai-fengyue-backend/backups/open-chat-20260721-160127/`。
- 两次整套部署均在上传前被 Paramiko 长连接重置；随后使用系统 OpenSSH 定向上传 6 个文件并带失败自动恢复，部署成功。
- 后端与 Nginx 均 `active`；内外 `/health` 为 `OK`；`CONTENT_MODE=local_only`；生产 DB `quick_check=ok`。
- 6 个线上源码 SHA-256 与本地完全一致；`open-chat-runtime.mjs` 返回 `200 text/javascript`。
- 生产域名内存测试卡在 390×844 成功挂载，`HomerChat/TavernHelper` 可用，父 DOM/localStorage 均不可读，横向溢出为 0，console/page error 为 0。截图：`output/playwright/open-chat-runtime-live-mobile.png`。
