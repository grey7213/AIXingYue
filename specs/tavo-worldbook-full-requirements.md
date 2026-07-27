# Tavo / 当前会话运行时配置需求

## 目标

参考用户提供的 Tavo 截图、APK 内置 JS-Slash-Runner 4.8.19 和现有 Open Chat Runtime，让惑梦 Web 在不拆除安全边界的前提下，补齐“当前会话预设”和“当前会话世界书”的悬浮管理能力，并让卡片内常用 TavernHelper 世界书函数真实读写当前会话。

## 本轮范围

- 在聊天设置中提供“当前会话配置”入口，使用挂载到 `body` 的居中悬浮窗，避免被顶栏或 `backdrop-filter` 改变 fixed 定位包含块。
- 预设页签显示当前生效的后台 Prompt 与 Regex 预设，支持搜索、逐项启停、当前筛选结果批量启用/停用和恢复继承值。
- 世界书页签读取锁定角色版本、当前会话 Mod、平台必需条目和当前会话新增条目，支持分组、搜索、逐项启停、批量启停和编辑允许字段。
- 会话覆盖只保存在 `user_id + conversation_id` 范围内，不改写后台全局预设、角色卡版本、Mod 版本或 `local_apps.extra_settings`。
- 平台必需反扒条目始终启用，不能删除、停用或修改正文。
- 新建会话默认继承；复制会话复制覆盖；删除会话清理覆盖。
- 普通对话的发送、流式发送、续写、重生成和新 Swipe 使用同一套覆盖；群聊不继承普通会话覆盖。
- iframe 继续使用 `sandbox="allow-scripts"` 且不加入 `allow-same-origin`。卡内通过白名单 postMessage RPC 调用当前会话能力，不能传入用户 ID、会话 ID、模型、积分或任意 URL。
- 兼容卡内常用函数：`getWorldbookNames`、`getGlobalWorldbookNames`、`getCharWorldbookNames`、`getChatWorldbookName`、`getWorldbook`、`replaceWorldbook`、`updateWorldbookWith`，以及基于它们实现的条目新增/删除助手。
- 世界书 RPC 使用 JS-Slash-Runner 常见 `WorldbookEntry` 外形，并保留服务端稳定 `source_key`，更新时执行字段白名单、数量和字符上限校验。

## 后续完整兼容范围

- Character Book/Tavo/SillyTavern 更多 camelCase/snake_case 字段的无损往返。
- sticky/cooldown/delay 的跨轮状态机、完整递归排除/阻止、分组 override/weight/scoring。
- 独立世界书导入导出、重命名和多本全局绑定管理。

## 验收

- 所有 UI 中标为可配置的字段必须真实影响下一次生成或回复后处理，不能只保存。
- Prompt 和 Regex 的逐项覆盖在总开关开启时生效；总开关关闭时整套停用，恢复后逐项覆盖仍保留。
- 世界书启停和编辑在下一次发送、续写、重生成、新 Swipe 中一致生效。
- 旧角色卡和现有对话不丢失；其他用户无法读取或修改该会话覆盖。
- 卡内 RPC 只能访问承载该 iframe 的当前会话；伪造来源和未知方法无效。
- 桌面与 375/390px 移动端无横向溢出，弹窗完整位于可视区域内，控制台/page error 为 0。
- 有 Python/Node 静态检查、本地临时 SQLite/API 往返测试、真实 Chromium UI 验证；部署后验证服务、Nginx、内外 health、`CONTENT_MODE=local_only` 和 SQLite `quick_check`。
