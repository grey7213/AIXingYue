# 惑梦网页端 APK 壳 Requirements

日期：2026-08-12

## 目标

把现有 APK 的用户入口改为当前惑梦（Homer）网页端，使 APK 启动后直接进入 `https://patcher.villainy.top/app/`，复用网站已有的登录、角色卡、聊天流式输出、群聊、记忆、制卡、农场、积分和充值兑换能力。

## 范围与验收标准

1. APK 保留包名 `org.nebula.horizon.composeai` 和现有签名升级路径。
2. 唯一桌面启动入口为 `HomerWebActivity`；旧 `MainActivity` 和旧充值页不再出现在 Launcher 中。
3. WebView 开启 JavaScript、DOM Storage、Cookie 持久化、文件选择和下载处理；返回键优先返回网页历史。
4. 仅允许 HTTPS 的惑梦站点在 WebView 内导航；外部支付/第三方页面交给系统浏览器，TLS 错误直接拒绝。
5. 网页主框架支持角色卡 JSON/PNG/ZIP 文件选择，以及网页请求的麦克风/相机权限回调。
6. 网络失败显示可重试页面；不在日志或错误界面输出 token、Cookie、API key。
7. 构建产物通过 apktool、`apksigner verify`、`zipalign -c` 和 `aapt dump badging`；有 ADB 设备时再做安装启动实测，无设备时明确标记未完成运行验证。

## 非目标

- 不把 SillyTavern/Node runtime 或后端数据库打进 APK，不承诺离线聊天。
- 不恢复普通用户 BYOK，不改变网站服务端鉴权、积分扣费或内容权限。
- 不公开许可证、源码入口或 GitHub 仓库链接。
