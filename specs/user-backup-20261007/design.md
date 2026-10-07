# 设计

## 调研与复用

2026-10-07 实时 GitHub API 检查：SillyTavern/SillyTavern 为活跃未归档 AGPL-3.0 仓库，open-webui/open-webui 活跃未归档、API 许可证为 NOASSERTION，不能按宽松许可证复制。已读现有固定 SillyTavern 的 `src/endpoints/users-private.js`，其 `/backup` 调用 `createBackupArchive` 并验证用户 handle；借鉴个人域 ZIP 下载方式。它只覆盖 runtime 目录，无法覆盖 Homer 的角色版本、人设和云端会话，且整目录可能包含模型密钥，所以不直接暴露其全量压缩接口。沿用标准库 zipfile/JSON 及现有 Store，避免引入新服务或数据库。

## 数据与接口

- 模块 `tools/homer_user_backup.py`，精确 `/console/api/web/user-backup/` 路由，在通用请求日志之前处理，备份正文不写 request_log。
- `GET download`：鉴权后导出当前账号，Content-Disposition attachment、private/no-store、nosniff。
- `POST preview` / `POST restore`：二进制 ZIP 上传，有压缩体积/展开体积/条目数/结构限制；不按 ZIP 路径解压。服务端重复校验；恢复在一个事务中写入私有副本及导入收据。
- 数据格式 `homer-user-backup`、schema_version=1、captured_at、scope、payload；文件 `backup.json`。显式字段白名单，关系 ID 重新生成；外部角色只保存引用，导入时重新查访问权限，不导出其私有提示词。
- 个人数据和服务器计费/权限数据分离。可恢复内容只写当前账号；不修改旧会话和公开角色。不以原 ID 直接覆盖任何已有对象。

## UI 交接（既有设置页的局部扩展）

入口沿用 `me.html` 的 profile-settings-routes；新 `/app/backup.html` 使用当前 app.css、surface-controls、主题与布局，无视觉重设计。桌面单列最大 760px；390px 主操作全宽。界面两张卡：下载备份、选择备份恢复；明确备份内容与时间、导入数量、私有副本规则、人设可选恢复；错误持久展示，解析/上传时禁用重复操作，成功显示计数。预览绝不渲染备份 HTML。截图检查明暗主题、窄屏长文件名、失败和成功状态。

Android 现有下载监听只把 HTTPS 交给外部浏览器，Blob 下载无效。新增仅限本站备份下载 URL 的 DownloadManager 路径，携带当前 Cookie，不将 Cookie 发给其他域名。旧数据与登录保留。新版 APK 同步 Web 入口。
