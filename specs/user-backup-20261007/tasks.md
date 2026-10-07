# 实施与验证

- [x] 线上逐文件哈希复核已有合并修复：456/456 与任务开始时源码一致，差异 0。
- [x] 阅读现有导入导出/版本/会话实现并进行开源调研。
- [x] 明确范围、接口、数据关系、导入策略与既有 UI 交接。
- [x] 实现后端导出、预览和原子导入，含边界测试。
- [x] 实现设置入口、下载、文件预览和恢复结果。
- [x] 完成 Android 保存与文件选择链路，构建签名候选 1.18.1 (354)，待上线验收后正式发布。
- [x] 本地往返、隔离、无覆盖、幂等、损坏/超限/权限 11 项通过；注册反馈 6 项通过。1440/390px 真实下载、预览、导入、损坏包拒绝及明暗截图通过，无横向溢出、无 page error。Pixel 6 API 33 实际 DownloadManager 保存 ZIP、系统文件选择器选择同一文件、预览和导入成功。
- [x] 生产备份后定向部署、临时夹具验收、健康与哈希复核。
- [x] 按 grey7213 身份提交 Web `f83346a` 与 Android `465e2a9`，PR #20 的 build 通过后快进合并，保留 Author/Committer 身份；正式 1.18.1 (354) 已发布。

## 本地候选验证

原生 clean bootstrap + 7 项 strict patches 成功；2161 个 Web 文件与主工作区比对无差异。既有 Node 回归 1698 通过、0 失败、1 可选跳过；Gradle testDebugUnitTest/lintDebug/assembleDebug/assembleRelease 通过。APK 1758 个清单项、524 个前端文件完整，原证书/v2/v3/zipalign 通过。

证据在 `output/user-backup-20261007/`，临时测试均为隔离本地账号。独立媒体文件和未同步设备草稿不包含在当前备份格式中，页面、README 和 scope 均明确，不称为完整媒体离线镜像。

## 正式交付（2026-10-07）

- 入口：`/app/me.html?panel=settings` → 本地备份 → `/app/backup.html`。新 APK 含入口及原生保存接口，旧 APK 下载须升级或使用手机浏览器。ZIP 和包内 backup.json 可预览/导入。
- 生产代码 6 个文件定向发布并逐一验哈希；最后另补“已删除角色不导出为现存创作”的过滤及回归，后端测试最终 12 项通过。原 456 个发布文件与主工作区复核依然 456/456 匹配。
- 生产真实 HTTP 验收：下载为 ZIP/attachment/private no-store；预览 1 角色/2 版本/1 会话/2 消息；恢复后数据正确，重复导入幂等，余额四项不变，request_log 没有备份正文。1440/390px 从设置真实点击入口，下载并选择文件、预览和恢复均成功；无脚本错误/横向溢出。
- 临时账号及 8 个测试角色、16 个版本、8 个会话、16 条消息、3 条导入收据已清理。最终数据库 quick_check=ok，测试用户/角色=0，未生成该测试账号的 runtime 数据目录；backend/dialogue/Nginx 均 active。未鉴权下载 401，退役页仍 404。
- Pixel 6 API 33 正式 353→354 覆盖安装成功，firstInstallTime 保持 `2026-09-22 11:04:46`，原登录/个人资料可见，设置中备份入口存在；进程日志无 FATAL EXCEPTION。原生 debug 变体已完成真正的系统 ZIP 下载、系统文件选择与恢复，非普通浏览器代替验证。
- 正式包 `E:/homer-user-backup-release/homer-1.18.1-354-release-signed.apk`，63,856,687 bytes，SHA-256 `bd0bf3c2f07f7ff18892e38206c63603fe22f4605c378ea56aabe1b8b097ce44`。原包名/证书、v2/v3、zipalign/1758 项资源通过。官网 immutable/canonical 均完整下载校验一致，GitHub asset digest 一致；release.json 为 354/no-cache。
- 官网：`https://patcher.villainy.top/download/homer-android-1.18.1-354-release.apk`；GitHub：`https://github.com/grey7213/homer-android-apk/releases/tag/release-1.18.1-354`。

## 发布前数据库恢复点

`E:/homer-backups/homer-prod-20261007-132412/` 为本轮数据库单项备份，301.6 MiB 压缩包解压为 3,009,613,824 bytes。初始直连 SCP 缓慢并断线，后以现有本地 HTTP CONNECT 代理承载 SSH/SFTP，先核验已下载前缀 SHA-256，再并行预取断点续传。服务器/本机最终 SHA-256 相同，真实解压 quick_check/integrity_check 均 ok；具体证据 `RECOVERED-MANIFEST.json` 与 `RESTORE.md`。

服务器保留压缩快照 `/root/homer-user-backup-deploy-20261007-061103/before.sqlite3.zst`；原代码备份同目录 `files/`，模块补充发布另存 `/root/homer-user-backup-deploy-20261007-062544/`。这是迁移后的当前数据，不恢复 10 月 3–6 日缺口；媒体/runtime 全量恢复源仍需单独保存。此次没有创建或改变定时任务。

## 仍需后续样本的问题

此前用户黑屏会话尚未提供账号和会话标识，本功能发布不等同于该问题已复现或修复；仍跟踪于 `../data-rollback-incident-20261007.md`。
