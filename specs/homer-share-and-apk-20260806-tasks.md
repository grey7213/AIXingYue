# 惑梦反扒卡分享包与 APK 构建 Tasks

日期：2026-08-06

| ID | 任务 | 状态 | 验证/备注 |
|---|---|---|---|
| HAP1 | 确认当前反扒世界书来源并与生产对比 | Done | 本地与生产 SHA-256 均为 `21FF7936C11FCCDE7884FAECB24B708CDD25561720157E1CEF2CAC2E46ABC21C`。 |
| HAP2 | 生成并复核反扒卡分享 ZIP | Done | `output/anti-scrape-card-20260806/homer-anti-scrape-card.zip`；4 个文件、3 条清单通过、Lorebook v2/1 条记录、秘密扫描 0。ZIP SHA-256：`4DBD8D759D8249FF7B4D50C0C3F5E9B5975C21855D282A1A20DB4BF9DDAEB52A`。 |
| HAP3 | 建立本次 requirements/design/tasks | Done | 本组三份 SPEC 已建立。 |
| HAP4 | 备份旧 APK、报告和签名信息 | Done | `output/apk-build-20260806/prebuild-backup/` 保存旧 APK、旧报告和不含密码/私钥的签名摘要；旧 APK SHA-256 为 `C4113F12725E2CE4F5060BBD65F4287791E540410B52A501BF6AEF5185124E26`。 |
| HAP5 | 使用现有流水线重建并签名 APK | Done | 使用 `--server-url https://patcher.villainy.top/ --xingyue-assets` 成功构建；流水线新增签名参数日志脱敏、支付 `return_url` 同步替换和真实 ADB 状态报告。 |
| HAP6 | 静态验证 APK 并整理交付副本 | Done | `output/apk-build-20260806/homer-android-20260806.apk`，`46431792` bytes，SHA-256 `8487C5FD182224B4DFC649BC2B0AD15658997F1F9CADB0B58155043BCCA82961`；包名 `org.nebula.horizon.composeai`、版本 `1.12.20 (260)`、标签 `AI星月`；v2/v3 签名和 zipalign 通过，证书 SHA-256 保持 `429B4165D958750C1FA90289C23B6D9B6D45FF915B535C5B1FBC72D52D93F320`；588 个代码/文本条目中目标域名命中 3、17 个旧上游域名命中 0，高置信凭据扫描 0。 |
| HAP7 | 更新项目记录并聚焦提交/推送 | Done | SPEC、导航和项目错误记忆已更新；output 产物与用户未跟踪 `.thm` 不纳入 Git。 |

## 当前限制

- 2026-08-06 `adb devices -l` 无连接设备，安装与真实启动验收待有设备后补做。
