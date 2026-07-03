# 酒馆功能补全 — Requirements

Captured: 2026-06-19. Owner skill: `ai-xingyue-patcher-ops`.

## 目标

`patcher.villainy.top/app/` 本质是一个「酒馆」（角色扮演聊天前端），UI 已做成 AI星月 风格，但功能只覆盖了酒馆的基础子集。目标：**在不改变 AI星月 UI 风格的前提下**，参照 SillyTavern 把「酒馆该有的核心功能」补齐，包括后端。

## 用户

- C 端用户：浏览/创建角色卡，与角色多轮 RP 聊天。
- 创作者：编辑功能完整的角色卡（性格/场景/示例对话/多开场白/世界书）。

## 现状（已实现，不动）

- 角色卡：name / summary / description / opening_statement(开场白) / pre_prompt(主提示) / tags / cover / bg / nsfw / 采样参数 / 模型预设。
- 聊天：多轮、会话落库、history_length 截断、OpenAI 兼容调用、每卡采样覆盖。
- 收藏 / 探索 / 我的角色 / 编辑器 / 积分。

## 缺失（本次补齐）— 对标 SillyTavern 核心

### Tier 1（RP 核心闭环，必做）
- R1 **开场白落为首条消息**：进入新会话时角色开场白作为第一条 assistant 消息出现（而非空白）。
- R2 **角色卡深度字段**：性格 personality、场景 scenario、示例对话 mes_example，注入系统提示。
- R3 **宏替换**：`{{char}}` / `{{user}}` / `{{name}}` 在所有提示词与开场白中替换。
- R4 **用户人设 Persona**：每用户保存 name + description，注入提示词作为 `{{user}}`。
- R5 **消息级操作**：重新生成(regenerate)、编辑(edit)、删除(delete)。
- R6 **swipe 备选回复**：assistant 消息可左右切换/生成多个备选。
- R7 **打字机呈现**：新回复逐字显现（前端模拟，低风险）。

### Tier 2（强酒馆特性）
- R8 **多开场白**：alternate_greetings，首条消息可 swipe 切换不同开场。
- R9 **世界书 / Lorebook**：每卡关键词触发的上下文注入。
- R10 **多会话**：同一角色可开多个独立对话 + 新建对话 + 删除对话。
- R11 **角色卡导入/导出**：兼容 SillyTavern Character Card V2 JSON。

### Tier 3（后续，非本次硬性目标）
- 群聊、自动摘要/记忆、TTS、表情立绘、指令模板管理。

## 验收标准

- AC1 进入任一 user/admin 角色聊天，立即看到开场白首条消息；含 `{{char}}/{{user}}` 的开场白已正确替换。
- AC2 编辑器可填写性格/场景/示例对话/多开场白/世界书并保存，重开编辑回填无丢失。
- AC3 聊天中可对 AI 回复「重新生成」「编辑」「删除」；重新生成产生新 swipe，可 ◀▶ 切换。
- AC4 在「我的」设置人设后，提示词中 `{{user}}` 替换为人设名，人设描述注入上下文。
- AC5 世界书条目命中关键词时其内容注入（可由「重新生成」对比体感验证）。
- AC6 可新建/删除会话；同角色多会话互不串。
- AC7 可导入一张 SillyTavern V2 角色卡 JSON 生成新卡；可导出自己的卡为 V2 JSON。
- AC8 UI 风格保持 AI星月（dark purple/pink star theme、glass、现有组件类）。无新顶层重设计。
- AC9 后端 `/health` 正常、现有 APK/旧端点不回归（catch-all 与既有路由不被新路由遮蔽）。

## 非目标

- 不重做 UI 视觉。
- 不引入新前端框架（继续 Alpine + 原生 ES module）。
- 不接入真实支付/真实 TTS。
- 本次不做群聊与自动摘要。
