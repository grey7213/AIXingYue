# 全局提示词与正则预设设计

## 数据模型

预设库保存在 `api_settings` 的两个独立 JSON 键中：

- `global_prompt_presets`
- `global_regex_presets`

两者结构均为 `{ active_id, items }`。每项有稳定 `id`、名称、来源、启用状态、导入文件名、完整条目和统计。旧 `global_prompt_preset` 单对象首次读取时兼容迁移为库中的 legacy 项，记录保留但可停用。

提示词项保留：

- 顶层兼容字符串字段。
- 每个 prompt 的原字段、未知字段、定义启用状态。
- prompt_order 中的顺序、启用状态、character_id。
- 未进入顺序表的定义，默认不参与运行时注入。

正则项保留 SillyTavern Regex 的全部字段和 ZIP 顺序。导入只接受安全 ZIP 路径中的 JSON，限制成员数、压缩后/解压后大小。

## API

- `GET /admin/api/global-presets`
- `POST /admin/api/global-presets/import-prompt`
- `POST /admin/api/global-presets/import-regex`
- `POST /admin/api/global-presets/{kind}/{id}`
- `POST /admin/api/global-presets/{kind}/{id}/activate`

所有接口要求管理员权限。保存详情和激活分离，避免模型配置保存误覆盖预设。

## 运行时

- 提示词：按当前预设的 prompt_order 读取启用且非 marker、非空内容条目；`chatHistory` 前进入 system 前置，之后进入 post-history。角色、模板宏和原始顺序保留。
- 正则：角色正则先执行，全局正则最后执行。
- prompt 阶段：处理当前用户输入和历史消息；按 placement、promptOnly/markdownOnly、minDepth/maxDepth 过滤。
- render 阶段：处理模型最终回复；只运行允许显示阶段的 AI output 脚本。
- 正则生成的 HTML 继续由 Web 聊天现有 sandbox iframe、CSP 和 URL 清洗器渲染。

## 后台页面

新增“全局预设”页，提示词与正则分栏。左侧是预设列表和唯一启用操作，右侧用折叠条目完整展示并编辑。导入使用本地 `.json`/`.zip` 文件，ZIP 以 Base64 交给服务端解析，不在浏览器执行。
