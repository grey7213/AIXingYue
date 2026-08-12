# 惑梦网页端 APK 壳 Tasks

日期：2026-08-12

| ID | 任务 | 状态 | 验证/备注 |
|---|---|---|---|
| HWA1 | 读取现有 APK 清单、流水线和网页入口 | Done | 确认旧 APK 是 Compose 原生页，当前网页入口为 `https://patcher.villainy.top/app/`。 |
| HWA2 | 建立 requirements/design/tasks | Done | 本组三份 SPEC 已建立。 |
| HWA3 | 注入 HomerWebActivity 并改唯一 launcher | Done | 最终 APK 仅含 `classes.dex`，清单只有 `HomerWebActivity` 一个 `MAIN/LAUNCHER`。 |
| HWA4 | 构建、签名、zipalign、静态扫描 | Done | `aapt` 确认 `1.12.21 (261)`、标签“惑梦（Homer）”；v2/v3 签名、zipalign 通过；证书 SHA-256 保持 `429b...f320`。APK 共 12 个条目，仅一个 `classes.dex`，无 assets/lib/旧 dex，17 个旧域名和 AI星月/AI风月文案命中均为 0。 |
| HWA5 | 真实页面/ADB 回归并更新项目记录 | Done | Pixel 6 API 33 模拟器安装和冷启动成功，前台为 `HomerWebActivity`，截图显示惑梦登录页；应用 PID 存活，logcat 无本应用 FATAL、旧品牌或旧域名。公网 390×844 浏览器登录页无横向溢出、无许可/GitHub 文案、page error=0。 |

## 最终产物与验证

- APK：`output/zip-1-repack/homer-web-apk-signed.apk`
- SHA-256：`51953f36bb6050aa1821fc3d3af5a3f6941fc569cb75e584e9345299b5f2960f`
- 包名：`org.nebula.horizon.composeai`
- 版本：`1.12.21 (261)`
- 启动 Activity：`org.nebula.horizon.composeai.ctf.HomerWebActivity`
- 模拟器证据：`output/zip-1-repack/homer-web-start.png`、`homer-web-ui.xml`、`homer-web-logcat.txt`
- 浏览器证据：`output/playwright/homer-apk-mobile-login.png`（验证产物，不提交 Git）
- 已知非阻塞项：登录页控制台仅有 Tailwind CDN 的生产环境 warning 和输入框 autocomplete 建议，无 JavaScript page error。
- 可重复性：已从原始 `base (1).apk` 完整重新解码，再剥离 `smali*`、assets、unknown、lib、旧 res 后构建/安装通过；中文长路径清理不是依赖历史 decoded 目录的偶然结果。
- 发布边界：部署器默认 APK 已指向新 Homer Web 壳，但本任务没有上传服务器，也没有重新公开 `/download/`。
