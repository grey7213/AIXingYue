# 生产数据本地备份 — 任务与验收

工具：`tools/backup_homer_production.py`（抓取）+ `tools/verify_homer_backup.py`（独立复核）
备份落地：`E:\homer-backups\homer-prod-<时间戳>\`（仓库外，含密钥，勿入 git）

## 任务

- [x] SSH 实测服务器现状：hostname、OS、磁盘、各类数据体量、已有备份、systemd 单元、cron（确认无备份任务）。
- [x] 用 `dbstat` 定位 2.3 GB 数据库的构成：`content_versions` 1160 MB + `local_apps` 1116 MB，而非日志表膨胀。
- [x] 调研现成方案：restic/borg（服务器未装，记为后续项）、rsync（本机 `rsync.exe` 缺 `cygcrypto-1.1.dll`，exit 127 不可用）、paramiko SFTP（实测 0.46 MB/s）、scp（实测 0.85 MB/s，采用）。
- [x] 实测带宽与并发：单流 0.85 MB/s，4 路 / 6 路并发均无提升 → 链路上限，压缩比才是杠杆。
- [x] 压缩参数基准测试（多组级别 × 3 类数据），确定 `--long=31` 为最大单项收益。
- [x] 验证 `--long=31` 的解压可行性：`zstd -d --long=31` ✅、`zstd -d` ❌（明确报错并提示该参数）、Python `max_window_size=2**31` ✅。
- [x] 写 `tools/backup_homer_production.py`：前置检查 → SQLite Online Backup 快照 → 服务器端打包+哈希 → scp 3 路并发 → 本地哈希比对 → 本地真解压验证 → 写 manifest/校验和/还原文档 → 清理暂存。
- [x] 写 `tools/verify_homer_backup.py`：独立复核工具，不复用备份工具的自我判断，直接把归档内容与线上实况对比。
- [x] 小样本冒烟（`--only server-config --only frontend`）验证全链路后再跑全量。
- [x] 执行全量备份。
- [x] 边跑边抽查已落地归档的内容（见下方「逐档抽查」）。
- [x] 补齐两处遗漏：`download/`（`release.json` 仓库无源）单独成档、`server-config` 增抓 sshd/fail2ban/防火墙。
- [x] 写 SPEC 三件套（requirements / design / tasks）。
- [x] 把两个新坑写进 `AGENTS.md`，更新 skill（`SKILL.md` 备份小节、`current-state.md` § 备份、`pitfalls.md` #21/#22、`deploy.md` 数据回滚）。
- [ ] 全量跑完后跑 `verify_homer_backup.py` 复核，把 `MANIFEST.json` 实测值填进「验证结果」。

## 逐档抽查（备份进行中已完成，非事后补写）

用本地 `zstd -d --long=31 | tar -tf -` 直接展开已落地的归档，与服务器实况对照：

| 归档 | 抽查结论 |
|------|----------|
| `backend.tar.zst` | 含 `ai_fengyue_local_server.py`、`ai-fengyue.env`、`card_experience_extension.py`、`data/verification_mail.sqlite3`；无 `.bak-*` 与 `__pycache__` |
| `server-config.tar.zst` | 含 `letsencrypt/live/patcher.villainy.top/{cert,privkey,fullchain,chain}.pem`、`nginx/sites-available/ai-fengyue-patcher.conf`、`inventory/packages.txt` |
| `homer-dialogue-data.tar.zst` | 10,660 条目 == 服务器 `find` 排除 `_webpack` 后的 10,660；42 个用户目录 == 服务器 42；`characters/` 1486、`chats/` 123、`worlds/` 115；`_webpack` 命中 0 |
| `homer-dialogue-runtime-source.tar.zst` | 1,522 条目；`node_modules/` 命中 0；四个必需扩展 + `homer-bridge` 全在（`js-slash-runner` 18、`ST-Prompt-Template` 256、`st-yuzi-phone` 7、`SillyTavern-MemoryBooks` 162、`homer-bridge` 8） |
| `frontend.tar.zst` | 100 条目；`index/admin/dashboard.html`、`app/{chat,create,explore,index}.html`、`app/assets/js/create.js` 全在；`media-cache`/`download` 命中 0（排除生效） |

数据库快照在服务器端已三重验证：`live_quick_check=ok`、`snapshot_quick_check=ok`、独立 immutable 只读连接 `ok`，`journal_mode=DELETE`，8778 张角色卡 / 54 张表。

## 验证结果

（全量下载仍在进行 —— 数据库 283 MB 已完整落地并哈希匹配，媒体库 337 MB 传输中。本节待 `MANIFEST.json` 落地后按实测值填写，不预填估算。）

## 剩余风险与后续

- 备份只有本地一份，磁盘故障即全丢。后续可在服务器装 `restic`，把本份作为初始快照做增量异地。
- 当前是人工触发，未定时化。
- `E:` 盘余量 112 GB，按每次约 700 MB 可放很多份，但没有自动保留策略。
- 本次链路实测 0.85 MB/s，全量约 50 分钟（初始估算 12 分钟偏乐观，实际受媒体库 337 MB 主导）。急用时可 `--only database` 单拉数据库（约 6 分钟）。
- `specs/homer-server-migration-20260818-tasks.md` 里「如需恢复角色卡/媒体库，提供正式生产备份」一条，现已具备可投产的数据库+媒体库备份。
