# 制卡架构源码导出设计

## 交付结构

```text
card-maker-source-export-20260715/
  README.md
  frontend/
  backend-reference/
  docs/
  examples/
  MANIFEST.sha256
```

## 组织方式

- 前端保留真实页面和模块源码，并带上最小共享依赖。
- 后端从当前单文件服务中整理制卡相关参考源码，避免把支付、认证密钥、用户数据与运维实现整体外发。
- 文档描述真实接口、数据结构、导入导出格式、运行时链路和安全边界。
- 示例只使用虚构、无版权和无用户数据的最小角色卡。

## 数据模型要点

- `local_apps.id`：内部业务主键，供会话、收藏、评论等引用。
- `local_apps.display_id`：公开短编号，不替代内部主键。
- `local_apps.extra_settings`：保存世界书、Regex、alternate greetings、Prompt blocks、quick replies、sampling 与扩展字段。

## 验证

- Python `py_compile` / JavaScript `node --check`。
- ZIP 解压测试和文件数核对。
- `MANIFEST.sha256` 逐项复核。
- 扫描密钥形态、敏感文件扩展名、真实用户/数据库产物和私有反扒内容。
