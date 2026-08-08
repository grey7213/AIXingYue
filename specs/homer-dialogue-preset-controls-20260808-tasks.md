# 惑梦对话预设可见性与操作收敛 Tasks

日期：2026-08-08

| ID | 任务 | 状态 | 验证/备注 |
|---|---|---|---|
| HDP1 | 建立 requirements/design/tasks 并登记导航 | Completed | 本组三份 SPEC 与 `specs/README.md` 已登记 |
| HDP2 | 强制停用 `st-yuzi-phone` 且保留扩展目录 | Completed | 默认设置、存量 settings 加载和 Homer 会话覆盖三层 disabled；桌面/390px JS/CSS 请求均为 0 |
| HDP3 | 删除全局“续写/重写/下回续”操作坞 | Completed | DOM/CSS 与生产 release 均无 dock；逐消息 continue/regenerate/next 真实生成通过 |
| HDP4 | 后台 Prompt 条目增加 `user_toggleable` | Completed | 缺失字段默认 false；管理员 Chromium 完成勾选、保存、重读、取消、恢复 |
| HDP5 | 服务端输出卡片全条目和官方公开条目 | Completed | 卡片 5/5 条目投影，官方只投影 3 个显式公开条目；Prompt 与反扒正文均未返回 |
| HDP6 | 收紧会话开关保存与历史覆盖过滤 | Completed | 伪造、隐藏、locked、未进顺序、跨卡、跨版本、非所有者全部拒绝；旧隐藏覆盖运行时失效 |
| HDP7 | 修复 OpenAI/Anthropic/ST bridge 真实生成覆盖 | Completed | 普通 OpenAI、普通 Anthropic、ST OpenAI、ST Anthropic 四类 payload 哨兵均通过 |
| HDP8 | 改造 Homer bridge 分组面板与切换 API | Completed | 角色卡/官方分组、锁定原因、会话持久化和 A/B 隔离通过 |
| HDP9 | 完成静态、后端和真实浏览器回归 | Completed | Python/Node/Git、自带两组 selftest、安全夹具、1440×900/390×844 Chromium、截图与反扒哈希均通过 |
| HDP10 | 更新 AGENTS、提交并推送 | In progress | 生产 release `20260808-213614` 已部署；待本地 commit/push，继续排除用户 `.thm` 与运行产物 |

## 当前约束

- 不修改或提交 `Tavo_主题效果_14G5y(1).thm`。
- 不打 APK。
- 不把反扒世界书、Prompt 正文、Cookie、Token、模型 Key 写入公开配置、日志或截图。

## 验证结果

- 后端安全夹具：`output/verify_homer_dialogue_preset_controls.py` 全部断言通过，SQLite `quick_check=ok`。
- 项目回归：`tools/_selftest_sillytavern_runtime.py` 与 `tools/_selftest_conversation_database.py` 全部通过。
- Chromium：原版 SillyTavern 1.18.0 在 1440×900、390×844 下加载完成，无横向溢出、console/page error；全局 dock 为 0，逐消息三种生成动作成功。
- 管理后台：5 个 Prompt 条目均出现“向用户显示并允许开关”，历史隐藏条目默认关闭，保存/重载与恢复往返成功。
- 反扒包：ZIP SHA-256 `5cc6dd8bd7f2b9eff795fdd0ebd472045beabb95172e26bb3867eb9efb54035d`；世界书 SHA-256 `21ff7936c11fccde7884faecb24b708cdd25561720157e1cef2cac2e46abc21c`，与站点权威文件一致。
- 生产：release `20260808-213614`；backend/dialogue/Nginx active，8008/8091 健康，公网 health/admin/chat 为 200，`CONTENT_MODE=local_only`，线上 7 个关键文件 SHA-256 与本地逐项一致。
- 通用 `verify_ai_fengyue_villainy.py` 在固定 `example.com` 验证邮箱处被 Resend 测试模式以 550 拒绝；生产邮件配置仍存在，属于该通用夹具的外部收件域限制，不是本轮对话改动回归。
