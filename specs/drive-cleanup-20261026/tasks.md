# 执行与验收

- [x] 根目录、项目规则、Git 工作树、文件大小、符号链接、关键资料盘点。
- [x] 确认 Android 真源、生产备份、签名与七个含未提交工作的目录必须保留。
- [x] 哈希归档根目录补丁与 R281 辅助文件：9 个文件，84,988,621 bytes，原名保留。
- [x] 13 个旧目录归档后移除原副本，12,376 个归档文件读回校验；8 组保留目录的 12,181 个文件迁移前后 SHA-256 一致，原有 Git 改动保留。
- [x] 主仓库、三个未完成工作树、生产备份、签名、正式 APK、离线别名均集中到 `E:/HomerWorkspace`；Git 工作树元数据和绝对 Junction 已修复。七个含未提交工作的旧目录均保留原文件或完整恢复快照。
- [x] 旧 `E:/z1` 的 19 个文件校验后移至 `legacy-apk/stage`，`E:/a` 别名移至 `legacy-apk/decoded`；仅移除失效的 `homer-apk-build`、`sttavo` 链接。
- [x] 清理六处明确的 Gradle 构建输出/缓存，释放 2,454,184,613 bytes；嵌套 `.web-cache/tree` 源码与生产备份全部保留。
- [x] 备份、构建、旧 APK 工具的默认路径及两份保留 Web 工作树中的同类路径已更新；新增固定工作树入口与项目目录规则。
- [x] CC Switch 4.0.10 同版本迁至 `E:/Tools/CC Switch`，程序 SHA-256 与原文件一致；进程响应正常，桌面、开始菜单、URL 协议及 Windows Installer InstallLocation 均正确。SQLite 检查 ok，providers/provider_endpoints/mcp_servers/prompts 四张配置表与迁移前逐行一致。
- [x] 15 个 Python 文件编译通过；实际导入确认全部默认目标存在；新工作树入口的预览、拒绝越界、拒绝既有目录、真实创建、干净移除五项检查通过；活动 tools 中未残留旧 `E:/homer-*` 默认路径。
- [x] E 盘根目录仅剩三个系统文件（`pagefile.sys`、`DumpStack.log`、`DumpStack.log.tmp`）；本次处理的旧 Homer 路径和散落文件均已移位或归档清理。
- [x] 清理清单、目录说明、恢复方法及独立 Git 备份文件范围已保存；提交结果另存清理归档中的 `git-backup-result.json`。

## 实测空间与证据

- 13 个旧目录原占 3,592,164,237 bytes，恢复 ZIP 占 1,439,020,344 bytes；加上构建缓存，按清单净减少 **4,607,328,506 bytes（约 4.29 GiB）**。
- E 盘空闲空间实测由 97,115,672,576 增至 101,702,213,632 bytes（约增加 4.27 GiB；与清单差异包含回退材料及同期磁盘写入）。
- 完整证据：`E:/HomerWorkspace/archives/2026-10-26/final-verification.json`、`retained-verification.json`、`snapshot-summary.json`、`actions.json`、`cache-deletion-plan.json`、`worktree-helper-verification.json`、`cc-switch/result.json`。
- 原有主仓库的 `plans/handoffs/HANDOFF_homer-281-release_2026-09-28.md`、`tools/push_homer_file.py` 及三个 `rc*.txt` 未纳入本轮提交。

## 后续约束

- 未完成社区/PR21 工作继续在固定 `worktrees/` 下进行。归档含私密测试资料与签名材料，保持现有 ACL，不上传公共仓库。
- 后续清理不可把 `.web-cache/tree`、业务数据库、WAL、生产恢复点或正式密钥当缓存；恢复旧 ZIP 时跳过根部过期 `.git` 指针并按 README 重建工作树。
