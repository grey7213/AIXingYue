# 惑梦反扒卡分享包与 APK 构建 Requirements

日期：2026-08-06

## 目标

- 将当前生产正在使用的反扒世界书整理为可直接转交的 ZIP 包。
- 使用仓库现有 Android 重打包流水线生成绑定 `https://patcher.villainy.top/` 的已签名 APK。
- 保留现有技术包名和升级兼容性；最新 Homer/SillyTavern 功能继续由服务端提供。

## 范围与验收标准

1. 反扒卡分享包
   - 来源固定为 `tools/data/tavo_anti_scrape_worldbook.json`。
   - 本地来源必须与生产服务器当前文件 SHA-256 一致。
   - ZIP 包含世界书、中文说明、元数据清单和 SHA-256 清单。
   - 解压后文件清单精确匹配，世界书为 Tavo Lorebook v2 且只有 1 条记录。
   - 高置信 API Key、Token、私钥扫描结果为 0；不在聊天回复中回显反扒正文。

2. APK
   - 构建前备份现有 APK、构建报告和签名验证信息。
   - 复用 `tools/zip1_repack_pipeline.py`，不临时新建未经验证的 WebView/Capacitor 工程。
   - 包名保持 `org.nebula.horizon.composeai`，内置节点绑定 `https://patcher.villainy.top/`，使用惑梦现有品牌资源。
   - 产物必须通过 APK 签名校验、4 字节 zipalign 校验和静态包信息检查。
   - 记录 APK SHA-256、文件大小、版本、启动 Activity 和证书摘要。
   - 若无 ADB 设备，明确标记未完成安装和真实启动验证，不伪造运行结果。

## 非目标

- 不把完整 SillyTavern Node runtime 离线塞入 APK。
- 不修改生产服务、数据库或域名配置。
- 不迁移历史包名、接口路径或签名体系。
- 不把签名密码、Token、Cookie 或私钥放进报告、提交或最终回复。
