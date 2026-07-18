# 创作中心完整角色资源包导入任务（2026-07-18）

- [x] 解析用户 PNG，确认当前卡片能力与缺口。
- [x] 审计扩展 ZIP、现有 Tavo 插件、世界书媒体绑定和卡片素材 API。
- [x] 合并独立资源包解析模块和本地 JSZip。
- [x] 在当前 `create.html/create.js` 上手工集成，不覆盖现有合并版本。
- [x] 补齐 ZIP bomb、JSON 大小、单素材和累计解压限制。
- [x] 完成单元测试、语法检查和临时后端 E2E。
- [x] 完成桌面/390px 浏览器导入、断点结构审查和 JSON/PNG 原入口回归。
- [x] 备份并部署，验证线上服务、health、MJS MIME、`CONTENT_MODE` 和 SQLite。
- [ ] 提交并推送 Git。

## 验证记录

- 正式模块安全测试 6/6、交付包功能测试 4/4；路径穿越、8MB JSON、20/30MB 单素材、768MB 累计解压和 512 文件限制生效。
- 本地真实 HTTP E2E：1 张卡、3 个 ready 素材、2 条世界书、1 条 Regex、2 条 `set_scene`，默认立绘/背景/BGM 正确；删除后卡、记录和素材文件均为 0，SQLite `quick_check=ok`。
- 浏览器 1440px/390px：导入链路全部 200，page/console error=0，按钮显示“导入卡包”，模块返回 `text/javascript`。
- 部署前备份：`/opt/ai-fengyue-backend/backups/card-pack-20260718-180816`，备份库 `quick_check=ok`。
- 线上：backend/Nginx active，内外 `/health` 为 OK，`CONTENT_MODE=local_only`，主库 `quick_check=ok`，`card-pack-import.mjs` 为 `200 text/javascript`。
