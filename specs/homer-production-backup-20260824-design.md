# 生产数据本地备份 — 技术设计

## 现状实测（2026-08-24，SSH 实测而非回忆）

```
hostname vm-851a1bc4a978a80f, Ubuntu 22.04 LTS, / 78G 用 16G (21%)
ai_fengyue.sqlite3          2,427,850,752 B   dbstat: content_versions 1160 MB + local_apps 1116 MB
media-cache                   425,413,265 B   8552 文件，1472 个内容完全重复
/var/lib/homer-dialogue       785,623,992 B   .jpg 378 MB + .png 291 MB + .jsonl 47 MB
/opt/homer-dialogue-runtime   4.0 GB          releases 2.9G（node_modules 344M/份）+ backups 1.2G
```

服务器已有工具：`zstd`、`pigz`、`rsync`、`python3`、8 核、7.9 GB 内存。未装 `restic`/`borg`。

## 先看现成方案（Foundational Engineering Mindset）

| 方案 | 结论 |
|------|------|
| **restic** / **borg** | 增量去重、加密、快照管理都成熟，是长期正解。但服务器未安装（需 `apt install`，动生产环境软件源），且首次全量仍要传全部数据 —— 本次要解决的是「一份都没有」，不是「省下次的带宽」。**本次不用，记为后续项。** |
| **rsync** 直拉 | 增量友好，但本机 `C:\Program Files\OpenSSH\bin\rsync.exe` 缺 `cygcrypto-1.1.dll` 起不来（实测 exit 127），Windows 侧不可靠。**弃用。** |
| **paramiko SFTP** | 部署脚本已在用，能复用连接。但实测下载只有 **0.46 MB/s**，比 `scp` 慢一半。**只用于执行命令，不用于传大文件。** |
| **scp**（Git 自带 OpenSSH） | 实测 0.85 MB/s，是本机最快通道。Windows 盘符会被 `host:path` 解析器误判，用 `cwd=目标目录` + 相对文件名规避（已实测通过）。**采用。** |
| 服务器已有的 `.tgz` 备份 | `/opt/homer-dialogue-runtime/backups/homer-dialogue-data-*.tgz` 是部署器留下的，但是**部署前**状态且只覆盖 dialogue 一类；`/opt/ai-fengyue-backend/backups/` 里的 2.4 GB 库是 08-20 的。都不能替代一份当前时点的完整备份。 |

## 关键决策：压缩参数

实测带宽只有 ~0.85 MB/s（4/6 路并发实测无提升，是链路上限而非并发数问题），所以**压缩比直接等于时间**。服务器压缩极快，压缩收益远大于 CPU 成本：

| 数据 | 参数 | 结果 | 耗时 |
|------|------|------|------|
| DB 2.32 GB | `zstd -8 --long=27` | 366 MB | 18s |
| DB 2.32 GB | `zstd -8 --long=31` | **301 MB** | 21s |
| DB 2.32 GB | `zstd -15 --long=27` | 329 MB | 103s |
| DB 2.32 GB | `zstd -15 --long=31` | 271 MB | 69s |
| media-cache 406 MB | `zstd -8 --long=27` | 367 MB | 6s |
| media-cache 406 MB | `zstd -8 --long=31` | **337 MB** | 4s |
| media-cache 406 MB | `zstd -12 --long=31` | 337 MB | 7s |
| media-cache 406 MB | `zstd -19 --long=31` | 336 MB | 47s |
| dialogue 749 MB | `zstd -8 --long=27` | 34.5 MB | 5s |
| dialogue 749 MB | `zstd -15 --long=31` | 33.3 MB | 22s |

两个结论：

1. **`--long=31`（2 GB 窗口）是本次最大的单项收益** —— DB 省 65 MB、media-cache 省 30 MB，因为这两份数据里有大量跨文件重复（media-cache 实测 1472 个完全重复文件；DB 里 `content_versions` 是 `local_apps` 的版本快照，内容高度相似）。窗口小于文件体量时 zstd 看不到这些重复。
2. **JPG 已经是压缩格式，压缩级别再往上几乎无收益**（media-cache 从 -8 到 -19 只省 1 MB 却多花 43s）。所以 payload 用 `-8`，只有数据库用 `-12`（多 20s 换 30 MB，按 0.85 MB/s 折算省 35s 传输，划算）。

`--long=31` 的代价是**解压端必须显式给同样的窗口**，否则报 `Frame requires too much memory for decoding`。已实测三条解压路径：

- `zstd -d --long=31` ✅
- `zstd -d`（不带参数）❌ 明确报错并提示 `Use --long=31`
- Python `ZstdDecompressor(max_window_size=2**31)` ✅（本机 zstandard 0.23.0）

这个坑必须写进 `RESTORE.md`，否则半年后拿到备份解不开。

## 架构

```
本地 Python (paramiko 执行命令 + scp 传输)
  │
  ├─ 1. 前置检查：hostname 核对、磁盘余量 ≥4 GB、解析 dialogue current release
  │
  ├─ 2. 服务器端 SQLite 一致性快照（不停服）
  │      sqlite3.backup() → journal_mode=DELETE → 独立 immutable 只读连接复验
  │      同时抓行数 + 表清单进 manifest
  │      （`--only` 不含 database 时跳过快照，只做只读普查，不白花 50s 和 2.3 GB 暂存）
  │
  ├─ 3. 服务器端暂存 server-config/（nginx、systemd、letsencrypt、sshd/fail2ban、19 份 inventory）
  │
  ├─ 4. 服务器端逐个打包 8 个归档 → /opt/homer-backup-staging/<stamp>/
  │      set -o pipefail（实测远端 shell 是 bash，支持）
  │      每个归档立刻在服务器算 sha256 + 体量
  │
  ├─ 5. scp 3 路并发下载 → 本地 sha256 与服务器端逐一比对（不一致直接抛错）
  │
  ├─ 6. 本地逐个真解压验证：
  │      普通归档 → 流式解压统计字节 + 哈希明文
  │      数据库   → 落地临时文件 → immutable 连接跑 quick_check + integrity_check + 行数
  │
  └─ 7. 写 MANIFEST.json / SHA256SUMS.txt / RESTORE.md
         全部通过后才删服务器暂存目录（失败则保留，可 --keep-staging 强制保留）
         清理失败只告警，不让已经落地并验证过的本地备份判为失败
```

独立复核工具 `tools/verify_homer_backup.py` 是第二道关，故意不复用备份工具的判断：

- `SHA256SUMS.txt` 与磁盘实际文件重算比对
- 每个归档流式展开，断言必含路径（env、systemd unit、TLS live 目录、homer-bridge、release.json 等）
- 数据库解压后与 **manifest 严格相等**（体量+行数），与**线上则只查方向**（`live >= backup`）—— 快照是时间点，用户/会话在快照后继续增长，相等反而是错的判据
- 媒体库文件数同理只查 `live >= archive`，另用蓄水池抽样取 6 张封面与线上逐字节 sha256 比对
- 生产健康：三服务 active、内外 `/health`、dialogue `/csrf-token`、model-presets 端点、暂存目录已清
- 支持只备份了子集的目录（按 manifest 里实际存在的归档决定查什么）

## 归档划分

| 归档 | 内容 | 排除 |
|------|------|------|
| `ai_fengyue.sqlite3.zst` | Online Backup 快照 | — |
| `media-cache.tar.zst` | 8552 张封面 | — |
| `homer-dialogue-data.tar.zst` | SillyTavern 每用户数据 | `_webpack` 构建缓存 |
| `homer-dialogue-runtime-source.tar.zst` | 当前 release 源码树 + `public/` | `node_modules` |
| `frontend.tar.zst` | 部署的站点 | `media-cache`、`download` |
| `download.tar.zst` | 公开 APK + `.sha256` + `release.json` | — |
| `backend.tar.zst` | 当前 `.py` + env + data 附属文件 | `*.bak-*`、`__pycache__`、`backups/`、live DB |
| `server-config.tar.zst` | nginx、systemd、letsencrypt、sshd/fail2ban、inventory | — |

`frontend` 归档排除 `media-cache`/`download` 是照 AGENTS.md 已记录的坑（未排除会让「源码包」膨胀到 GB 级）；`backend` 归档排除 live DB 是避免同一份 2.3 GB 数据传两遍。

`download/` 单独成档而不是并入 frontend：实测服务器上 4 个 APK 里有 2 个（`ai-xingyue-latest.apk`、`homer-android-1.13.0-debug.apk`，sha256 `20715a1f…`）能在本地 `output/apk-runtime-20260819/` 找到同哈希副本，但 **`release.json` 全仓库搜不到任何来源** —— 它是 2026-08-19 发布时直接在服务器上生成的。这类「只存在于生产」的小文件正是备份要抓的东西；单独成档也让将来换成几十 MB 的正式签名包时不会污染源码归档。

`server-config` 除了 nginx/systemd/TLS，还抓了 `sshd_config`+`sshd -T` 生效值、`fail2ban` jail、`ufw`/`iptables` 规则 —— 2026-08-18 那轮 SSH 加固的结果不在仓库里，重装机器时这是唯一参照。

## 安全约束

- 全程只读生产数据：唯一的写操作是在 `/opt/homer-backup-staging/` 下建临时文件，`chmod 700`，结束即删。
- 不碰服务器上任何已有备份目录（`/opt/*/backups/`、`/root/homer-*-backup-*`）。
- 不 `cat` env/密钥内容到日志或工具参数 —— env 只以文件形式进 tar，凭据值不出现在任何输出里。
- `MANIFEST.json` 用 `contains_secrets` 字段显式标注哪些归档含密钥；`RESTORE.md` 开头就是「这个目录含密钥」警告。
- 备份目录放 `E:\homer-backups\`（仓库外），避免任何 `git add` 误伤；仓库 `.gitignore` 本身也已忽略 `*.zst` 之外的 `*.sqlite3`/`*.tgz`/`*.zip`。

## 风险

| 风险 | 处理 |
|------|------|
| 传输中断（0.85 MB/s，全量约 12 分钟） | 归档留在服务器暂存目录，重跑 `--only <name>` 即可；哈希不匹配直接抛错不静默 |
| 服务器磁盘被暂存塞满 | 前置检查要求 ≥4 GB 余量（实际需 ~700 MB）；当前 62 GB 可用 |
| 备份期间数据库被写入 | Online Backup API 本身处理并发写；快照后立即复验 `quick_check` |
| 半年后解不开归档 | `RESTORE.md` 写明 `--long=31` 必需，并给出三条已实测的解压路径 |
| 误以为备份成功但文件是空/坏的 | 本地真解压 + 数据库 `integrity_check` + 行数比对，任一失败即抛错 |

## 后续项（不在本次范围）

- 服务器侧装 `restic`，把这份全量作为初始快照，后续增量到本地或对象存储。
- 定时化（`cron` + 保留策略），当前是人工触发。
- 备份目录异地副本。
