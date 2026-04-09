# 兼容性说明

本文档用于说明 Claude Anywhere 当前对不同后端的能力边界、显式拒绝策略，以及一些已知限制。

## 总体原则

Claude Anywhere 的目标不是“尽量偷偷兜底”，而是：

- 能安全转换的请求就转换
- 不能安全表达的请求就显式报错
- 尽量保持 Claude Code 需要的工具协议语义

这意味着某些场景下你会收到明确的 `400` 错误，而不是一个看起来成功、实际语义已经丢失的请求。

## 当前后端能力矩阵

### OpenAI-compatible

当前行为：

- 支持普通文本请求
- 支持 Anthropic `tool_use` / `tool_result` 到 OpenAI-style `tool_calls` / `tool` 消息的转换
- 会对消息做一次 OpenAI-compatible 归一化处理

当前限制：

- 默认不支持 Anthropic `thinking`
- 不支持 `top_k`
- 当前代理层不支持 image content block 透传，会显式报错

可选策略：

- 当设置 `UNSUPPORTED_THINKING_BEHAVIOR=map` 时，OpenAI-compatible 路径可以尝试把 Anthropic `thinking` 映射到 `reasoning_effort`
- 映射值由 `THINKING_TO_REASONING_EFFORT` 控制，默认是 `low`
- 这是近似映射，不保证与 Anthropic 原生 `thinking` 完全等价

### Gemini

当前行为：

- 支持普通文本请求
- 支持工具调用协议转换
- 会对工具 schema 做 Gemini 兼容性检查

当前限制：

- 不支持 Anthropic `thinking`
- 不支持 `top_k`
- 对工具 schema 比较严格，如果包含 Gemini 不支持的字段会直接拒绝

当前会显式拒绝的典型 schema 字段：

- `additionalProperties`
- `default`
- 某些当前适配层不接受的 `format`

### Anthropic

当前行为：

- 支持原生 Anthropic 路径
- 支持 `thinking`
- 支持 `top_k`
- 支持图片输入

## 当前显式拒绝的请求

下面这些场景当前会直接返回错误，而不是继续降级：

- 非 Anthropic 后端请求中使用 `thinking`
- 非 Anthropic 后端请求中使用 `top_k`
- `tool_choice` 类型非法
- `tool_choice.type="tool"` 但未提供工具名
- `user` 消息中出现 `tool_use`
- OpenAI-compatible 后端下传入 image content block
- Gemini 工具 schema 中包含当前适配层不支持的字段

## 工具调用兼容性

当前已经覆盖的核心工具语义：

- assistant `tool_use` -> backend `tool_calls`
- user `tool_result` -> backend `tool` role message
- backend `tool_calls` -> Anthropic `tool_use`
- 多轮工具调用后的继续推理链路

## 已有测试覆盖

当前测试已经覆盖：

- `tool_result -> tool` 消息转换
- `tool_calls -> tool_use` 响应转换
- 非法 `tool_choice` 显式报错
- `user` 消息错误携带 `tool_use` 显式报错
- OpenAI-compatible 图片输入显式报错
- Gemini 不兼容 tool schema 显式报错
- OpenAI / Gemini / Anthropic adapter 基础路径
- `/v1/messages` 接口级 `400` 返回

## 尚未完整覆盖的场景

下面这些场景建议在后续继续补测试：

- 多工具并行调用
- 流式 tool 参数增量输出
- Claude Code 更真实的 shell / file tool schema
- 不同 OpenAI-compatible 平台之间的细节差异

## 使用建议

如果你准备用这个代理接第三方 OpenAI-compatible 平台，建议优先验证：

1. 纯文本对话
2. 单工具调用
3. 多轮工具调用
4. 流式工具调用

如果前两步正常、后两步异常，通常不是 Claude Code 的问题，而是目标平台在 function calling 或流式 tool call 语义上的兼容度不足。
