# 服务端多音色 TTS 需求

- 不再使用浏览器 `speechSynthesis`。
- 登录用户只能朗读属于自己的 assistant 消息。
- 提供普通话、粤语、台湾口音的多种男女音色。
- 音频由服务端生成并缓存，相同文本和音色不重复合成。
- 不向前端暴露密钥；单条文本限制 1200 字并清理 HTML/脚本。

当前采用无需 API Key 的 `edge-tts` 服务端代理；后续可替换为 Apache-2.0 Kokoro/CosyVoice provider。
