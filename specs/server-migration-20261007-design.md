# 全服务器迁移设计

## 当前验证

- 源：Ubuntu 22.04、x86_64、78 GiB 根盘，约 34 GiB 已用；12 个业务容器及多个 systemd 业务服务。
- 目标：CentOS 7、x86_64、50 GiB 根盘，约 1.2 GiB 已用、7.6 GiB RAM；未发现 Docker/业务目录。SSH 已验证，已添加现有备份公钥，未存储密码。
- CentOS 7 与旧机运行时差异大且已终止维护；已询问用户通过云厂商面板重装 Ubuntu 22.04，备份工作继续，新机部署待系统决定。

## 复用与依据

复用 `tools/backup_homer_production.py` 和 2026-10-02 的逐项目备份/验证脚本。采用 SQLite Online Backup、PostgreSQL pg_dump、MySQL/MariaDB single-transaction、tar/zstd、Docker save/export；不为一次迁移引入新备份平台。2026-10-07 已在线访问官方文档：

- https://www.sqlite.org/backup.html
- https://www.postgresql.org/docs/current/app-pgdump.html
- https://docs.docker.com/engine/storage/volumes/
- https://www.centos.org/centos-linux-eol/

逐项目逻辑备份用于可恢复数据库；补充主机持久文件归档保留原有脚本、日志、历史材料、账号/服务配置。虚拟文件系统、运行 socket 和本次备份自身不收入递归归档。在线文件归档不是整机同一瞬间快照；切换前必须执行一致性收尾。

## 执行与保护

用户已重装目标为 Ubuntu 22.04，SSH 密码登录和公钥登录均验证；云镜像原设 PubkeyAuthentication=no，备份配置后用 drop-in 启用公钥并通过 sshd -t。旧机随后失联，本机和目标机交叉验证均超时；用户选择恢复 10 月 2 日备份。新的在线备份没有成功，不作为恢复来源。

当前执行路径改为：本地旧备份重新哈希校验 -> 加密上传至目标 root-only 目录 -> 解压/数据库恢复 -> 非遗本地最新资产补齐 -> 所有业务验收与 DNS 切换。历史 10 月 2 日数据库为权威恢复来源，不从本地开发库覆盖其他业务。

恢复盘点补充：中转站本地独立仓库另有同日更晚的已验证 `backups/villainy-sub2api-backup-20261002-141047.zip`，包含 Sub2API 0.2.11 的数据库、Compose、品牌前端及 Nginx。优先采用这份完整、相互匹配的恢复点，替代早间整机备份里的 0.2.0；其他服务仍用整机备份。非遗 JSON/密钥采用用户明确授权的本地 `output/private-portal-data`，它是本地状态而非生产快照，最终报告必须说明来源。

1. 盘点源/目标、DNS、服务、挂载、镜像、数据库、计划任务与外部 IP 依赖。
2. 新日期目录备份，低优先级限制压缩线程；本地 `E:/server-backups/server-20261007/` 与 `E:/homer-backups/` 限权。旧备份保持不变。
3. 目标系统准备后服务器间加密传输，校验归档；目标配置修改前另作备份。
4. 在不接公网业务和不启动重复任务的情况下恢复、验证；保持原版本、数据库主版本、UID/GID、TLS 和域名。
5. 最终同步并切换域名/流量；保留旧机作为恢复点，检查 DNS、HTTP、证书、服务和业务数据。

所有包含环境变量、Docker inspect、数据库、TLS、SSH 材料的输出仅存于 root-only/受限 ACL 目录。验收报告只给数量、哈希、路径及状态。
