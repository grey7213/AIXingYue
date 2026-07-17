# RP Hub 互动卡与官推卡池任务（2026-07-16）

- [x] 读取项目规则、技能状态、相关 Web/SillyTavern SPEC。
- [x] 提取目标 PNG 元数据，确认 Vue UI、弹窗和 GitHub MP3 依赖。
- [x] 实现受限 RP Hub 外部资源与父窗口兼容。
- [x] 实现官推字段、后台管理和首页随机展示。
- [x] 完成本地语法、SQLite/API 和浏览器验证。
- [x] 部署并验证线上服务、页面、数据库与安全回归。
- [x] 更新项目错误记忆、任务记录，提交并推送聚焦改动。

## 2026-07-18 验收

- 官推池本地验证公开已发布过滤、随机池读取和 3+ 官推时普通推荐彻底排除官推卡；生产字段/索引存在，当前池为空时按设计回退普通卡。
- RP Hub 目标 PNG 实际导入并启动对话：5 首 BGM 被提取，序章翻页可交互，内联脚本全部可解析；父 DOM/localStorage 不可读，iframe 无 `allow-same-origin`。
- 修复目标卡 JSON 字符串内未转义 `style="..."` 导致 `Unexpected identifier 'color'` 的兼容问题；旧 Tavo sandbox/CSP/resize 线上回归全部通过。
