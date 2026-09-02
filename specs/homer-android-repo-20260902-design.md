# 惑梦 Android 交付仓设计（2026-09-02）

## 问题

`android-app/` 的源码不在任何版本控制内，只存在于 `E:\homer-apk-1140`（从交接 ZIP
抽出来的目录）。两个后果：那个目录删了就得重新从 ZIP 取；别人想改原生壳只能靠
「打个更新包发给我」。

更新包这条路已经烧过三次。包都从 `AIXingYue-main.zip` 分叉，不是从当前 HEAD，
按 README 说的「按相同相对路径覆盖」会静默退掉之后改回的生产修复 ——
r1 那次会退掉 `homer-bridge/index.js` 的三处已上线修复，r2 想退掉 `chat.js` 的
Java 桥 receiver 修复。这些回退在 diff 里看不出来，它们表现为「包里是旧代码」。

## 目标

- 原生壳有版本控制的真源，别人能 clone、改、开 PR
- web 端保持单一真源（`AIXingYue`），不出现第二份
- web 改动的交付方式在结构上无法静默回退
- 成品 APK 不进任何 git 历史
- PR 有自动校验，挡掉编译不过、补丁对不上基线、新文件没进包这三类返工

## 仓库拆分

| 仓库 | 可见性 | 内容 |
| --- | --- | --- |
| `grey7213/AIXingYue` | 公开 | 主仓库。web 端真源，完整工作区 |
| `grey7213/homer-android` | 私有 | `main`：原生壳 + 脚本；`web-base`：web 两棵树的孤立分支 |
| `grey7213/homer-android-apk` | 私有 | 只走 Releases |

两个新仓库都私有：原生壳源码、内置补丁机制、服务端职责文档不适合公开。
代价是贡献者要逐个邀请为 collaborator（`push` 权限），Actions 分钟数计费。

## web 端为什么不进 homer-android

`frontend/` 9.2 MB + `sillytavern-runtime/` 131 MB。塞进去有两个问题：
一是 `main` 从 1.8 MB 涨到 140 MB，二是 web 出现第二份真源，两边各改一处时
必然重演静默回退。

选的方案：`web-base.json` pin 一个 commit，`tools/bootstrap.py` 稀疏浅检出到
`.web-cache/tree`，再在仓库根建目录联接。Gradle 的 `syncHomerClientAssets` 从
`rootProject.projectDir.parentFile` 读那两棵树，所以链接位置必须是仓库根。

用链接而非复制，是为了让 `export_web_patch.py` 能直接 `git diff` ——
改 web 文件时改的就是那个 git 检出本身。Windows 上用目录联接（`mklink /J`），
不需要管理员权限，也不要求开开发者模式；符号链接两者都要。

### 为什么 web-base 是 homer-android 的孤立分支，而不是直接拉 AIXingYue

初版方案是让 bootstrap 直接从公开的 AIXingYue 按 SHA 取。实测两个障碍：

1. GitHub 默认拒绝 `git fetch <任意 SHA>`（`upload-pack: not our ref`），
   只能抓 ref。
2. 主仓库本地有 7 个未推 commit，含 101 个 web 文件改动。贡献者从公开 main
   拉到的是旧代码，构建出来的包和我手上的对不上。

要解决 2 就得推那 7 个 commit 到公开仓，但它们包含运维脚本：root SSH 登录、
密钥文件名、`/opt/homer-dialogue-runtime` 与 `/opt/ai-fengyue-backend` 的布局、
备份与发布流程。没有密码或密钥，但等于公开一份服务器地图。IP 本身已经公开
（DNS 就能解出 `38.76.218.46`），布局不该再加。

改成在 homer-android 里开孤立分支 `web-base`，只含那两棵树。`tools/push_web_base.py`
从主仓库 HEAD 取 tree、`commit-tree` 造孤立提交、推上去、更新 pin。
校验过 `web-base:frontend` 与主仓库 `HEAD:frontend` 的 tree SHA 逐字节一致。
公开仓一个字不动，`main` 保持 1.8 MB，贡献者本来就有这个私有仓的权限。

## web 改动为什么走 patch

补丁头部记基线 commit，落地走 `git apply -3`。三方合并的三种情形都实测过：

| 情形 | 结果 |
| --- | --- |
| 维护者没动过该文件 | 干净落地 |
| 维护者改过同一文件的不同位置 | 自动合并，两边改动都保留 |
| 维护者改过同一行 | `with conflicts`，文件里留 `<<<<<<< ours` 标记 |

第三种恰恰是覆盖式交付会静默吃掉改动的情形。补丁把它变成显式冲突。

`--binary --full-index` 两个开关是必须的：前者保住图片改动，后者让 `git apply -3`
能查到 blob 做三方合并。新增文件靠 `git add -N`（intent-to-add）进 diff。

`.gitattributes` 里 `*.patch -text`：CRLF 转换会让 `git apply` 报 corrupt patch。

## 两道防白屏的闸

`syncHomerClientAssets` 的失败模式是安静的 —— web 树没装配或新文件没同步，
构建照样成功，只是包里少文件，运行时 `import` 404、页面白屏，编译期看不出来。
`page-cache.js` 就这么让探索页和「我的」页白屏过。

1. `app/build.gradle` 配置期检查 `frontend/` 与 `node_modules/webpack` 是否就位，
   缺了直接抛 `GradleException` 并说「先跑 bootstrap」。
2. `tools/verify_apk_assets.py` 逐个核对 `frontend/` 下文件在 APK 里有没有条目，
   同时查 runtime 的 `lib.js` 不是空的。

第 2 条按 aapt 规则跳过点开头的路径（`.well-known/`、`.gitkeep`）——
核对过生产 267 包，同样缺这 3 条，是 aapt 的既定行为不是漏。
拿 265 的包做反向验证：确实报出缺 `page-cache.js`，正是当初那个事故文件。

## CI

`ubuntu-latest`，JDK 21 + Node 20 + 预装的 Android SDK。流程：装配工作区 →
落地 PR 内 web 补丁（`--strict`，基线不符直接失败）→ `testDebugUnitTest` +
`assembleDebug` → 校验资源完整性 → 传 debug APK 当 artifact（14 天）。

`.web-cache` 整体走一个缓存 key（`node_modules` 就在它里面，分两个缓存会因路径
重叠打架）。私有仓的 `web-base` 靠一条 `url.insteadOf` 全局改写规则带上
`github.token` —— `actions/checkout` 的凭据只写进它自己的 `.git/config`，
bootstrap 在 `.web-cache/tree` 另起仓库拿不到。

## 成品包

APK 单包 40 MB 以上。三个方案对比：

- 直接 commit：每包永久 +40 MB，`git rm` 删不掉，克隆越来越慢
- Git LFS：免费额度 1 GB 存储 / 1 GB 月流量，约 24 个包就满
- Releases 附件：不进 git 对象库，仓库保持几十 KB —— 选这个

## 遗留与风险

- `E:\homer-apk-1140` 仍是我的出包工作区，方向变成 homer-android → 1140 单向同步。
  两边都改会重演分叉，`MAINTAINER.md` 里写了同步命令。
- `web-base` 每次推进都是 force push 一个新孤立提交，约 140 MB 上传。
- pin 更新后必须把 `web-base.json` 提交到 `main`，否则贡献者 bootstrap
  报「基线动了而 pin 没跟上」。`push_web_base.py` 结尾会提示这条命令。
- 贡献者拿不到正式签名私钥，交的都是 debug 包。正式签名仍在我这边。
