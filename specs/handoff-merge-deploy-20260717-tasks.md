# 惑梦前后端交接合并任务（2026-07-17）

- [x] 读取技能状态、项目规则、交接日志、快照说明和相关 SPEC。
- [x] 备份当前工作树并隔离解压交接 ZIP。
- [x] 完成 Git 基线/当前工作区/交接快照三方差异与安全边界分析。
- [x] 合并正式前后端源码，排除数据库与开发临时文件。
- [x] 完成语法、模块、临时 SQLite、API 和安全回归。
- [x] 完成桌面与 390px 浏览器全页面及重点交互回归。
- [x] 备份生产环境并重新部署前后端。
- [x] 完成线上服务、数据库、API、浏览器和业务回归并清理临时数据。
- [x] 更新 AGENTS、验收记录，提交并推送聚焦改动。

## 验证记录

- 交接 ZIP SHA-256 为 `0D13849EEC24CEFFAE01D27008FE01007569B74477988281D0C0A87D08FADA9F`；只合并正式源码，未上传包内 SQLite、WAL/SHM、开发脚本、pyc 或样本文件。
- 修复交接遗漏：普通推荐同时排除所有 `official_recommended` 卡；RP Hub 内联状态脚本把未转义 `style="..."` 转为 HTML entity 后再在隔离 iframe 执行。
- 本地：全部改动 JS/MJS `node --check`、3 个 Python `py_compile`、卡片扩展 3 项测试、schema 3 项测试、Cookie/Bearer/积分/官推/导入/Galgame/SQLite 集成回归通过。
- 浏览器：16 个页面在 1440 和 390 宽度均 HTTP 200、无横向溢出、console/page error=0；数据合并页导入 4 项并导出 2 条世界书，恶意名称未执行；Shadow runtime 的 Galgame、BGM 列表、live 字段、搜索筛选、insert-text 和 XSS 清理通过。
- RP Hub 样本 `黎明之契2.71`：5 首 BGM 列表、序章翻页交互和内联脚本解析通过；iframe 为 `sandbox=allow-scripts`、无 same-origin，父 DOM 与 storage 不可读。
- 旧 Tavo 回归：本地与线上 `verify_tavo_sandbox_browser.py`、`verify_tavo_advanced_render_browser.py`、`verify_chat_resize_mobile.py` 全部通过，console/page error=0。
- 生产备份：`/opt/ai-fengyue-backend/backups/handoff-merge-20260717-165600`，SQLite 在线备份 `quick_check=ok`。
- 部署后：backend/Nginx active，Nginx 配置通过，内外 `/health=OK`，`CONTENT_MODE=local_only`，生产 SQLite `quick_check=ok`；`.mjs=text/javascript`，`/app/data-merge.html=200`，本地/线上关键文件 SHA-256 一致。
