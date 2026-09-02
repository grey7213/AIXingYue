# 惑梦 Android 交付仓任务（2026-09-02）

设计见 [homer-android-repo-20260902-design.md](homer-android-repo-20260902-design.md)。

## 已完成

### 1. 建两个私有仓库
- `grey7213/homer-android` —— 原生壳源码 + 装配脚本，默认分支 `main`
- `grey7213/homer-android-apk` —— 成品包交付，只走 Releases

### 2. 原生壳进版本控制
`E:\homer-apk-1140\android-app` 的 49 个源文件迁入 `homer-android/android-app`，
排除 `.gradle/`、`app/build/`、`local.properties`。`main` 首个提交 4597 行、仓库 1.8 MB。

`gradlew` 的可执行位单独补了一个提交 —— 从 Windows 工作区 add 进来是 100644，
首次 CI 在 Linux runner 上报 `Permission denied` exit 126。

### 3. web 基线分支
`homer-android` 的孤立分支 `web-base` = 主仓库 `HEAD` 的 `frontend/` +
`sillytavern-runtime/` 两棵树。校验过 tree SHA 与主仓库逐字节一致：
`frontend` `3811bb48`，`sillytavern-runtime` `cbc45cec`。

### 4. 脚本
| 脚本 | 作用 |
| --- | --- |
| `tools/bootstrap.py` | 装配可构建工作区：检出 web 基线、建目录联接、装 node 依赖、生成 `local.properties` |
| `tools/export_web_patch.py` | web 改动 → 对着基线 commit 的 git patch |
| `tools/apply_web_patches.py` | 把 `web-patches/` 的补丁三方落地（CI 用 `--strict`） |
| `tools/verify_apk_assets.py` | 核对前端与运行时资源真的进了 APK |
| `tools/push_web_base.py` | 维护者推进 web 基线并更新 pin |

### 5. 两道防白屏的闸
`app/build.gradle` 配置期检查 web 树与 webpack 是否就位；`verify_apk_assets.py`
逐文件核对包内资源。

### 6. CI
`.github/workflows/pr-build.yml`：装配 → 落地补丁 → 单测 + assembleDebug →
校验资源 → 传 debug APK（14 天）。

### 7. 文档
- `README.md` —— 仓库分工、快速开始、环境要求
- `CONTRIBUTING.md` —— 贡献者八节操作手册，含自查清单和 9 条报错对照
- `MAINTAINER.md` —— 我这边收 PR、落地补丁、出正式包、推进基线、邀请协作者
- `homer-android-apk/README.md` —— 交付方式、tag 规范、签名边界

## 验证结果

| 项 | 结果 |
| --- | --- |
| `bootstrap.py --check` | 5 项环境全部识别 |
| `bootstrap.py` 从零装配 | web 基线检出 + 目录联接 + `npm install --omit=dev`，webpack 就位 |
| `testDebugUnitTest` | 17 个全过 |
| `assembleDebug` | 出包 45.2 MB，2 分 30 秒 |
| `verify_apk_assets.py` 本地 debug 包 | 通过，109 个前端文件全在包内，`page-cache.js` / `dialogue-prewarm.js` 确认打进去 |
| `verify_apk_assets.py` 反向验证 265 包 | 正确报出缺 `page-cache.js`，exit 1 |
| patch 干净落地 | 通过 |
| patch 同文件不同位置 | 自动合并，两边改动都保留 |
| patch 同一行 | `with conflicts`，留 `<<<<<<< ours` 标记 |
| Gradle 缺 web 树时 | 抛 `GradleException` 并提示跑 bootstrap |
| `push_web_base.py --dry-run` | 基线未变时正确判定「无需推进」；`source_commit` 改掉后正确造出孤立提交 |
| CI run#1 | 失败于 `./gradlew: Permission denied` —— Windows 上 add 进来是 100644，已用 `update-index --chmod=+x` 修 |
| CI run#2 | 全绿，2 分 08 秒（冷缓存：装配 15s、构建 93s） |
| CI run#4 | 全绿，1 分 30 秒（热缓存：缓存命中 3s、构建 74s） |
| PR #1 的 CI | 全绿 —— 即去掉凭据改写后的 workflow 首次验证 |
| PR #1 squash 合并 | 成功，走的是完整的「CI 绿灯 → squash → 删分支」路径 |

## 转公开（同日追加）

两个仓库都转为 public。带来的三处变更：

### main 的保护规则

公开仓能免费用 ruleset。开了 `main 保护`（id `22080138`）：

| 规则 | 效果 |
| --- | --- |
| `pull_request` | 不能直推 `main` |
| `required_status_checks` = `build`（strict） | CI 绿灯且分支跟上 `main` 才能合 |
| `non_fast_forward` | 禁 force push |
| `deletion` | 禁删 `main` |

bypass 给 `RepositoryRole` id 5（admin），我推 `web-base.json` 的 pin 不必绕 PR。

双向实测：撤掉 bypass 时我自己直推被 `push declined due to repository rule
violations` 挡下，加回来才通。CI 上报的 check 名确认是 `build`，与规则一致 ——
名字对不上会让所有 PR 永远卡在「等待 build」。

### CI 去掉凭据改写

原有一步 `git config --global url.insteadOf` 把 `github.token` 注进全局，
让 bootstrap 在 `.web-cache/tree` 里能拉私有的 `web-base`。公开后多余，删掉。
无凭据 `git fetch --depth 1 origin web-base` 实测通过。

### 转公开前的凭据审计

- `android-app` 追踪文件：无密码/密钥赋值；URL 全是 `example.test`、`127.0.0.1`、
  RFC1918 私网地址和 `schemas.android.com`
- `main` 全历史扫 private key / AWS / GitHub token / keystore 口令：无
- 历史里无 `.keystore`/`.jks`/`.pem`/`.key` 文件
- web 树扫赋值型凭据：无
- MAINTAINER.md 原写了 keystore 文件名、alias、证书指纹 —— 指纹用
  `apksigner verify --print-certs` 从已发布 APK 就能读出（实测确认
  `429b4165…f320`），不算秘密，但 alias 和位置挪去 `AGENTS.md`

### 文档改双轨

fork 路线（任何人，我零操作，首个 PR 要我点 Approve and run）与 collaborator
路线（省掉 fork，发 Release 的必要条件）。`read`/`triage` 建不了 Release。

## 待办

- [ ] 收第一个外部 PR，验证补丁落地流程在真实分歧下的表现
- [ ] 有人要发 Release 时给 homer-android-apk 的 write

## 风险

- `E:\homer-apk-1140` 仍是出包工作区，方向是 homer-android → 1140 单向同步；
  两边都改会重演分叉
- pin 更新后忘记把 `web-base.json` 提交到 `main`，贡献者会卡在「基线不符」
- `web-base` 每次推进 force push 约 140 MB。`non_fast_forward` 只作用于
  `~DEFAULT_BRANCH`，不挡 `web-base`
- 仓库无 LICENSE 文件。构建编入 AGPL-3.0 的 SillyTavern，README 已说明，
  但本项目自有代码的许可仍未声明


