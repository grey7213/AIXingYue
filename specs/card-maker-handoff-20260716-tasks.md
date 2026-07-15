# 制卡器交接功能任务（2026-07-16）

- [x] 读取项目规则、技能现状、相关 SPEC、ZIP 文档和对接清单。
- [x] 解压并验证 ZIP：35 项 Manifest 匹配，Node 3/3、Python 3/3 测试通过。
- [x] 实测新密钥兼容 CelestiAI；`/models` 返回 6 个 Gemini 模型，真实 `gemini-2.5-flash-cli` 请求成功。
- [x] 实现独立 Gemini 分组和模型价格展示。
- [x] 实现反扒世界书服务端私有化、partial update 修复和存量清理。
- [x] 实现本卡 Prompt Preset 导入、开关、运行时与 V2/PNG round-trip。
- [x] 实现农场全解锁门槛、管理员用户白名单与创作页权限提示。
- [x] 按交接清单实现互动素材前后端、存储、运行时和删除清理。
- [x] 完成本地单元/集成/浏览器验证。
- [x] 备份、部署、写入新模型 preset、迁移线上数据并完成线上验收。
- [x] 更新 AGENTS/任务记录，提交并推送聚焦改动。

## 当前约束

- 不触碰工作区中用户已有的 `app.css`、`workshop.html`、Tavo 文件和截图改动。
- 密钥不得写入源码、SPEC、日志、Git 或最终回复。

## 2026-07-16 验收记录

- 本地静态：后端/扩展/部署脚本 `py_compile`、全部改动 JS/MJS `node --check`、`git diff --check` 通过；ZIP 原始 Node 3/3、Python 3/3 继续通过。
- 本地集成：`output/card-maker-handoff-20260716/verify_integrated_card_maker.py` 验证锁定/管理员开放/农场 8 地、素材三阶段与跨所有者拒绝、服务端 URL、反扒详情/V2/PNG 隐藏与运行时首位、本卡预设独立性/密钥清洗/导入默认关闭、模型唯一 ID 与统一价格。
- 浏览器：桌面和 390px 创作页无横向溢出；锁定态显示 `2/8` 且高级导入禁用；后台显示“未开放/农场全解锁/后台开放”；互动 Shadow DOM 弹窗、侧栏、场景、标记清理通过，作者 script/style 未进入运行时，console error=0。
- 线上备份：`/opt/ai-fengyue-backend/backups/card-maker-20260715-192247`；迁移备份 `/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-card-maker-20260715-192400.sqlite3`；模型配置备份 `/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-gemini-20260715-192843.sqlite3`，均 `quick_check=ok`。
- 线上迁移：扫描/更新 8475 张富字段卡，移除 8475 条平台反扒副本；现库 `quick_check=ok`。
- 线上模型：原 CelestiAI 48 + 独立 Gemini 6，共 54 个唯一 ID/模型，默认仍为原 minimal，全部公开显示 `50 惑梦币/次`，无敏感字段；两个分组真实生成各扣 50。
- 线上素材/权限：未开放、管理员 override、农场 49 天/8 地三种状态通过；跨所有者完成上传被拒，MP3 Range 返回 206，公开 URL 为服务端可信路径；测试用户/卡/会话/素材均清理为 0。
- 线上页面：三个 `.mjs` 均返回 `200 text/javascript`；CSP `worker-src 'self'`；移动端创作页 54 个模型分两组且全部带价格，聊天模型面板同样为 48+6，console error=0。
