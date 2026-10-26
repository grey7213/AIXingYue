# 目录与迁移设计

- 固定工作区：`E:/HomerWorkspace/`。Android/Node 旧工具需要 ASCII 路径，Web/backend 真源继续为 `E:/酒馆开发`。
- `android/`：独立 Android 真源；`build/`：现用出包工作区；`worktrees/`：仍有未提交工作的隔离 Git 工作树；`backups/`：完整保留的生产恢复资料；`archives/2026-10-26/`：散落文件与旧工作区恢复快照；`signing/`：本地签名交接；`releases/`：已发布包；`offline/`：本地运行别名。
- 先枚举真实目录、Git 状态、Junction、签名和运行进程，再制定精确迁移/删除列表。移动前检查绝对路径与边界，目标存在则中止，禁止覆盖。
- 保留所有未提交内容。干净工作树删除前保存独有的 ignored 输出，Git 分支/历史保留；无法证明是可重建缓存的内容归档。Junction 只操作链接本身，禁止跟随删除目标。
- Android 主仓库移动后修复 worktree 元数据及内部绝对 Junction；迁移前后比对 Git 状态和文件哈希。
- 活跃工具统一引用固定工作区，历史报告保留历史路径并由当前 AGENTS/目录映射解释；不重新执行旧的一次性改码脚本。
- 旧 APK 构建工具的 `E:/a` Junction 和 `E:/z1` 暂存移至 `legacy-apk/decoded`、`legacy-apk/stage`；仅移除已经失效的 `E:/sttavo` 链接，逆向源码与密钥不删除。明确生成的三个 `android-app/app/build` 与其 `.gradle` 缓存可重建并清理，`.web-cache/tree` 的嵌套 Git 和未提交补丁保留。
- CC Switch 使用 Windows Installer 同版本迁移或经验证的可回退本地迁移，先备份程序和设置，更新入口并实测新进程路径。
- 本次为现有文件的本地运维与明确路径修正，复用 Git worktree、PowerShell 文件 API、Windows Installer；无需新框架或开源选型调研。
