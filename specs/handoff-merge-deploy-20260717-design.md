# 惑梦前后端交接合并设计（2026-07-17）

## 合并策略

- 以 Git `HEAD` 为共同基线，对比当前工作区与交接快照。
- 当前工作区独有改动原样保留；重叠文件采用已确认包含 RP Hub/官推逻辑的交接后续版本。
- 正式源码只接收 `frontend/`、`tools/ai_fengyue_local_server.py` 和 `tools/card_experience_extension.py` 的已审计差异。
- 排除 `output/`、SQLite、`__pycache__`、开发守护/代理脚本及临时验证产物。

## 功能边界

- 卡片体验继续在 Shadow DOM 与无 `allow-same-origin` iframe 中运行，声明式动作由主站运行时代理。
- 运行时新增多曲 BGM、音量、Galgame 对话层、实时字段同步、卡内搜索/筛选和安全的输入框文本注入。
- 制卡器新增 Galgame 配置、素材情绪标签与对应服务端白名单归一化。
- 角色导入兼容顶层 `beginning`、`regex_scripts` 和受限 RP Hub BGM 元数据。
- Web 登录使用 HttpOnly Cookie，Bearer token 仍保留给 APK、管理脚本和兼容客户端；公开响应不暴露服务端秘密。
- 官推字段只允许管理员维护，首页只展示公开且已发布的池内角色。

## 部署与回滚

- 部署前分别备份生产后端目录、前端目录、Nginx 站点配置和主 SQLite。
- 使用既有部署助手上传正式源码，不上传本地数据库。
- 健康轮询等待 SQLite 初始化完成后再判断服务状态。
- 若出现启动、迁移或核心回归失败，恢复同批次备份并重新验证健康与数据库完整性。
