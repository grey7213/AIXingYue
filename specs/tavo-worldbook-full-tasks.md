# Tavo / 当前会话运行时配置任务

- [x] 核对 APK 内 JS-Slash-Runner 4.8.19、现有 Open Chat Runtime、Mod 合并和空世界书 bridge。
- [x] 明确当前会话覆盖的数据边界、API、生成顺序和安全 RPC 设计。
- [x] 新增会话预设/世界书覆盖 schema、Store CRUD、复制和删除清理。
- [x] 实现 runtime-config、preset-overrides、worldbook-overrides API。
- [x] 将覆盖接入 blocking、SSE、continue、regenerate 和新 Swipe。
- [x] 完成聊天页预设/世界书悬浮窗、批量操作和世界书编辑器。
- [x] 将 TavernHelper / JS-Slash-Runner 世界书空实现替换为受限 RPC。
- [x] 完成 Python/Node 检查、本地临时库/API/运行时测试和 Chromium 桌面/390px 验证。
- [ ] 更新项目错误记忆、部署备份、线上验收、提交并推送。（错误记忆/部署/线上验收已完成，待提交推送）

## 本地验收结果（2026-07-28）

- Prompt/Regex 逐项覆盖、世界书编辑/新增/替换、平台必需条目锁定与正文隐藏通过。
- 非所有者访问 404；复制继承覆盖；删除会话清理覆盖。
- 发送、续写、重生成和新 Swipe 均使用当前会话覆盖，SQLite `quick_check=ok`。
- Chromium 1440×960 与 390×844 悬浮窗均在视口内、无横向溢出；iframe RPC 可连续读写且父 DOM/localStorage 不可读，伪造来源无效，console/page error=0。
- 生产域名当前会话配置弹窗在桌面/390px 均完整位于视口内，遮罩覆盖完整、无横向溢出，console/page error=0。

## 后续完整兼容

- [ ] sticky/cooldown/delay 跨轮状态机。
- [ ] 完整递归排除/阻止和分组 scoring/override/weight。
- [ ] 独立世界书导入导出、重命名和多本绑定管理。
