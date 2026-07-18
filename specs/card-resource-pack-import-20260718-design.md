# 创作中心完整角色资源包导入设计（2026-07-18）

## 文件与页面

- 新增 `frontend/app/assets/js/card-pack-import.mjs`：只负责压缩包解析、世界书/Regex 合并、素材推断和最终绑定 payload 生成。
- 本地提供 JSZip 3.10.1 及许可证，不依赖外部 CDN。
- `create.html` 扩展导入 accept 和脚本加载；`create.js` 编排基础卡导入、素材上传、断点重试和最终 update。

## 数据流

1. 浏览器校验压缩包大小和扩展名，JSZip 仅读取内存，不写本机路径。
2. 读取 manifest/card/worldbook/regex，并限制 JSON 大小。
3. 校验素材数量、单文件未压缩大小和累计未压缩大小，再生成 File 对象。
4. 调用现有 `/cards/import` 创建基础卡。
5. 对每个素材调用 upload-intent、对象 PUT、complete；记录 `pack_index` 和已完成进度。
6. 根据 `bind_world` 或目录推断建立 `world_info[].media_bindings`，写入默认素材与 `set_scene` 规则。
7. 调用同一卡片 update；失败时保留页面内任务并只继续未完成阶段。

## 兼容边界

- 资源包 `.tpg` 与后台 Tavo 插件 `.tpg` 共享扩展名但协议不同：创作中心要求存在角色卡 JSON；后台插件要求插件 manifest。
- 服务端继续重建可信媒体字段，客户端 URL 不是权威。
- 场景规则只引用当前卡已完成且归属当前用户的素材 ID。

