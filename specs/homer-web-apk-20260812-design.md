# 惑梦网页端 APK 壳 Design

日期：2026-08-12

## 方案选择

采用现有 APK 的注入式 WebView 壳，而不是临时新建 Capacitor/TWA 工程。这样能保留包名、签名和升级路径，并直接获得生产网页端的全部最新功能；TWA 需要浏览器/数字资产链接配置，Capacitor 会引入新的 Gradle 工程和插件维护成本。该方案的明确边界是在线应用：账号、模型、聊天和积分仍由 `patcher.villainy.top` 服务端提供。

## Prior art（2026-08-12 实查）

- Android `views-widgets-samples`：Apache-2.0，仓库已归档；基础 WebView API 仍由 Android 平台维护，可作为实现模式参考，但不直接复制归档示例工程。
- `GoogleChrome/android-browser-helper`：Apache-2.0，未归档，2026-07-30 仍有更新；适合 TWA，但需要受支持浏览器和 Digital Asset Links，且会改变当前注入式 APK 发布链。
- `ionic-team/capacitor`：MIT，未归档，2026-08-11 仍有更新；生态成熟，但引入新的 Gradle/Node 插件工程、同步流程和升级成本。
- 结论：当前是已签名 APK 的定向升级，原生平台 WebView 的适配成本最低，也最容易保持现有包名/证书；TWA/Capacitor 保留为以后新建正式 Android 工程时的候选，不在本次临时迁移。

## 启动与安全边界

```text
Launcher -> HomerWebActivity -> WebView -> https://patcher.villainy.top/app/
```

- 同源 `patcher.villainy.top` 页面留在 WebView。
- 其他 HTTPS 主机用系统浏览器打开；非 HTTPS 导航拒绝。
- WebView 禁止混合内容、文件 URL 访问和调试；Cookie 由系统 CookieManager 持久化。
- 文件选择通过系统 `ACTION_OPEN_DOCUMENT`，不把本地文件路径暴露给网页。
- 只有该站点来源的音频/视频权限请求可被转交给 Android 运行时权限。

## 构建流

```text
base (1).apk / decoded workspace
  -> remove legacy Compose dex/native/webapp payload
  -> inject HomerWebActivity as primary classes.dex
  -> make it the only launcher
  -> rebuild only the minimal app label/theme/icon/network resources
  -> apktool build -> zipalign -> apksigner
```

## 验证

- 静态：Manifest 只有一个 `MAIN/LAUNCHER`，其 Activity 为 HomerWebActivity；APK 中有 Homer URL，旧上游节点为 0。
- 页面：真实浏览器访问 `/app/`、登录页和移动宽度布局；WebView 运行时若有设备则检查 URL、标题、错误页和返回键。
- 运行：记录 ADB 是否存在，绝不以构建成功代替安装启动成功。
