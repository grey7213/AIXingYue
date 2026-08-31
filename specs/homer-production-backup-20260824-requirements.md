# 生产数据本地备份 — 需求

## 背景

Homer（惑梦）生产服务器 `38.76.218.46` 上有约 3.6 GB **无法从本仓库重建**的数据，此前**本地一份都没有**：

| 数据 | 位置 | 体量 | 为什么不可重建 |
|------|------|------|----------------|
| 业务数据库 | `/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3` | 2.3 GB | 8778 张角色卡（含 `content_versions` 版本快照）、30 个用户、77 个会话、站点文案与 LLM 预设 |
| 封面媒体库 | `/var/www/ai-fengyue-frontend/media-cache` | 406 MB | 8552 张 JPG，被 `local_apps.cover_url` 直接引用 |
| 对话运行数据 | `/var/lib/homer-dialogue` | 749 MB | SillyTavern 每用户 characters/chats/worlds/settings |
| 发布产物 | `/var/www/ai-fengyue-frontend/download` | 240 KB | `release.json` 是 2026-08-19 发布时在服务器上生成的，仓库里搜不到任何来源 |
| 服务器配置 | nginx / systemd / env / letsencrypt / sshd / fail2ban | < 1 MB | env 含 Resend+ZPAY 凭据，TLS 私钥不可再生，2026-08-18 那轮 SSH 加固结果不在仓库里 |

`specs/homer-server-migration-20260818-tasks.md` 里「如需恢复角色卡/媒体库，提供正式生产备份」这一条一直悬着，就是因为没有这份备份。服务器 2026-08-15 已经被服务商维修重装并换过一次 IP，这个风险是实际发生过的。

## 目标

1. 把上述四类数据完整拉到本地磁盘，形成一个自包含、可校验、带还原说明的备份目录。
2. 过程只读，不影响线上服务：不停服、不改动生产数据、不删除服务器上任何已有备份。
3. 每个归档都做端到端完整性校验，而不是「传完就算成功」。
4. 沉淀成可重复执行的项目工具，而不是一次性命令堆。

## 验收标准

- [ ] 本地备份目录包含数据库、媒体库、对话数据、前端、公开下载目录、后端、运行时源码、服务器配置八个归档。
- [ ] 数据库快照用 SQLite Online Backup API 生成，`journal_mode=DELETE`（不留 `-wal`/`-shm`），服务器端与本地解压后 `quick_check` 与 `integrity_check` 均为 `ok`。
- [ ] 每个归档服务器端 sha256 == 下载后本地 sha256，且本地能真正解压（不只是校验哈希）。
- [ ] 备份目录内有 `MANIFEST.json`（含行数、哈希、体量、耗时、排除项原因）、`SHA256SUMS.txt`、`RESTORE.md`（逐步还原命令）。
- [ ] 有一个独立复核工具，不复用备份工具的自我判断，能把归档内容与线上实况对比。
- [ ] 生产侧验收：备份前后 backend/dialogue/Nginx 均 active，`/health` 正常，数据库行数不减少。
- [ ] 服务器临时暂存目录在全部本地校验通过后才删除；失败时保留以便重试。

## 非目标

- 不做异地/云端同步（S3、rclone）。本次只要本地一份可用副本。
- 不做增量或去重仓库（restic/borg）。服务器未装，且首份全量备份优先级更高。
- 不备份可重建物：`node_modules`（用 `package-lock.json` + `npm ci` 恢复）、`_webpack` 构建缓存、APK 产物、服务器上已被本次快照取代的历史备份（`/opt/ai-fengyue-backend/backups/` 2.4 GB、`/opt/homer-dialogue-runtime/backups/` 1.2 GB）。
- 不做自动定时任务。本次是人工触发的工具，定时化留作后续。
- 不在备份过程中清理服务器磁盘（当前 78G 用 16G，不紧张）。
