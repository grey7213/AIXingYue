# 惑梦反扒卡分享包与 APK 构建 Design

日期：2026-08-06

## 方案选择

本次不是新建 Android 客户端，而是对已完成 Web/SillyTavern 验收的项目做发布打包。仓库已有并长期验证的 Compose APK 反编译重打包流水线，因此直接复用 `tools/zip1_repack_pipeline.py`。当前没有新的 Gradle/Capacitor Android 工程；临时创建壳工程会改变包名、签名和升级路径，也无法离线承载依赖 Node 的 SillyTavern runtime，故不采用。

外部开源调研不属于本次已有流水线的重复选型范围；Android 基础壳、apktool、zipalign 和 apksigner 均沿用仓库锁定工具链及历史实现。

## 反扒卡包

```text
tools/data/tavo_anti_scrape_worldbook.json
  -> 与生产文件 SHA-256 对比
  -> 生成 README.zh-CN.md / manifest.json / MANIFEST.sha256
  -> homer-anti-scrape-card.zip
  -> 独立目录解压复核、逐文件哈希和敏感信息扫描
```

分享包只包含使用所需内容，不包含后台配置、数据库、日志或服务器凭据。

## APK 构建流

```text
base (1).apk / 已解码工作区
  -> 替换内置服务器节点为 https://patcher.villainy.top/
  -> 应用惑梦品牌资源和兼容补丁
  -> apktool build
  -> 注入既有兼容 dex
  -> zipalign
  -> 复用现有 keystore 签名
  -> apksigner / zipalign / aapt 静态验收
  -> output/apk-build-20260806/ 最终副本
```

构建脚本日志对 `--ks-pass`、`--key-pass` 等参数值做脱敏，签名密码不进入控制台记录。

## 验证

- ZIP：文件数、清单、JSON 解析、schema/entry 数、来源 SHA、高置信秘密扫描。
- APK：`apksigner verify --verbose --print-certs`、`zipalign -c -p -v 4`、`aapt dump badging`。
- 静态内容：确认目标域名存在，旧上游节点不再作为内置可选节点；检查关键品牌资源和 launcher。
- 运行时：仅在 ADB 有设备时安装启动。本次若设备为空，只交付静态已验证 APK。
