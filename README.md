# Claude Anywhere

一个面向 Claude Code 的协议适配代理。

Claude Anywhere 的目标，是让依赖 Anthropic `messages` 协议的客户端，能够稳定接入 OpenAI-compatible、Gemini 以及 Anthropic 等不同模型后端，同时尽可能保留 Claude 风格的工具调用体验。

它不是一个只做“文本转发”的轻量代理，而是一个把协议兼容、工具链语义、错误边界和后续可维护性放在前面的工程化实现。

## 为什么做这个项目

很多客户端默认围绕 Anthropic 协议设计，尤其是 Claude Code 这类重工具调用场景。问题在于：

- 不同模型后端的协议并不一致
- 工具调用字段看起来相似，但真实语义并不完全兼容
- 某些代理方案能跑通普通对话，但在多轮工具调用、流式 tool call、schema 兼容性上容易出问题
- 当请求不兼容时，静默降级往往比直接报错更难排查

Claude Anywhere 选择的路线是：

- 对可安全转换的能力做显式适配
- 对不可安全表达的能力明确报错，或按策略降级
- 保持 Claude Code 这类客户端依赖的工具调用语义
- 用可拆分的模块结构支撑后续扩展

## 设计理念

### 1. 以协议语义为中心

Claude Anywhere 关注的不只是把字段名改掉，而是尽量保留请求和响应在工具调用上的真实语义，包括：

- `tool_use`
- `tool_result`
- backend `tool_calls`
- 多轮工具调用后的继续推理

### 2. 显式兼容性优先于静默降级

对于无法安全表示的能力，默认优先返回明确错误，而不是偷偷吞掉字段或改成普通文本。这样问题更早暴露，也更容易排查。

### 3. 模块化适配，而不是单文件堆逻辑

项目当前已经拆分为：

- `proxy_core/models.py`：请求/响应模型与模型映射
- `proxy_core/compatibility.py`：兼容性校验与显式报错
- `proxy_core/capabilities.py`：后端能力矩阵
- `proxy_core/conversion.py`：Anthropic <-> LiteLLM 协议转换
- `proxy_core/streaming.py`：流式响应转换
- `proxy_core/adapters/`：不同 provider 的适配器

### 4. 面向 Claude Code 真实使用场景优化

项目优先关注的不是“最少代码跑通一个 demo”，而是这些更真实的问题：

- Claude Code 能否稳定走完工具调用链路
- 多轮 `tool_result` 后能否继续推理
- 不同 provider 的边界是否明确
- 流式和非流式返回是否都能保持 Anthropic 风格

## 项目能力

当前项目主要提供这些能力：

- 接收 Anthropic 风格的 `/v1/messages` 请求
- 将 `haiku`、`sonnet` 等 Claude 模型名映射到你配置的后端模型
- 在 Anthropic 风格的 `tool_use` / `tool_result` 与后端 function calling 格式之间做转换
- 支持流式和非流式响应
- 支持 provider adapter 结构，便于扩展不同后端
- 提供显式兼容性检查，而不是把所有问题都留给底层后端报错

## 当前状态

这个仓库目前以“手动构建、手动运行”为主：

- 不提供预构建镜像
- 不提供托管服务
- 需要你自己配置 API Key
- 需要你自己在本地或服务器上运行代理

## 环境要求

- Python 3.10 及以上
- 可用的后端 API Key
- `conda`、`uv` 或普通 Python 虚拟环境均可

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/striveBin/Claude-Anywhere.git
cd Claude-Anywhere
```

### 2. 配置 `.env`

先复制示例文件：

```bash
cp .env.example .env
```

然后根据你的后端情况修改 `.env`。

OpenAI-compatible 接口示例：

```dotenv
PREFERRED_PROVIDER=openai

OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1

BIG_MODEL=your-large-model
SMALL_MODEL=your-small-model
```

Gemini 示例：

```dotenv
PREFERRED_PROVIDER=google
GEMINI_API_KEY=your-gemini-key

BIG_MODEL=gemini-2.5-pro
SMALL_MODEL=gemini-2.5-flash
```

Anthropic 示例：

```dotenv
PREFERRED_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-key
```

可选配置：

```dotenv
UNSUPPORTED_THINKING_BEHAVIOR=error
THINKING_TO_REASONING_EFFORT=low
```

说明：

- `error`：非 Anthropic 后端收到 `thinking` 时直接报错
- `drop`：自动忽略 `thinking` 并继续请求
- `map`：在支持的后端上尝试映射到 `reasoning_effort`

## 安装依赖

### 使用 conda

```bash
conda create -n claude-proxy python=3.11 -y
conda activate claude-proxy
pip install fastapi[standard] uvicorn httpx pydantic litellm python-dotenv google-auth google-cloud-aiplatform
```

### 使用 uv

```bash
uv sync
```

如果你不使用 `conda` 或 `uv`，也可以直接根据 `pyproject.toml` 自己安装依赖。

## 本地启动

### 方式一：Windows + conda + PowerShell

#### 1. 进入项目目录

```powershell
cd D:\Desktop\Claude-Anywhere
```

#### 2. 准备 `.env`

如果你还没有 `.env`：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，填入你的后端配置。

#### 3. 安装依赖

```powershell
conda create -n claude-proxy python=3.11 -y
conda run -n claude-proxy python -m pip install fastapi[standard] uvicorn httpx pydantic litellm python-dotenv google-auth google-cloud-aiplatform
```

#### 4. 启动服务

```powershell
conda run -n claude-proxy python -m uvicorn server:app --host 0.0.0.0 --port 8082
```

开发模式：

```powershell
conda run -n claude-proxy python -m uvicorn server:app --host 0.0.0.0 --port 8082 --reload
```

#### 5. 验证服务

```powershell
Invoke-WebRequest -Uri http://localhost:8082/ -UseBasicParsing
```

#### 6. 连接 Claude Code

临时方式：

```powershell
$env:ANTHROPIC_BASE_URL="http://localhost:8082"
$env:ANTHROPIC_API_KEY="dummy-key"
claude
```

或者写入 `C:\Users\WINDOWS\.claude\settings.json`：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8082",
    "ANTHROPIC_API_KEY": "dummy-key"
  },
  "model": "haiku"
}
```

### 方式二：Linux / macOS

#### 1. 进入项目目录

```bash
cd Claude-Anywhere
```

#### 2. 准备 `.env`

```bash
cp .env.example .env
```

#### 3. 安装依赖

```bash
uv sync
```

或者：

```bash
python -m pip install fastapi[standard] uvicorn httpx pydantic litellm python-dotenv google-auth google-cloud-aiplatform
```

#### 4. 启动服务

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8082
```

开发模式：

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8082 --reload
```

#### 5. 验证服务

```bash
curl http://localhost:8082/
```

#### 6. 连接 Claude Code

```bash
ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY=dummy-key claude
```

## Docker 构建

项目提供了基础 `Dockerfile`，但当前仍然推荐自行构建镜像。

### 构建镜像

```bash
docker build -t claude-anywhere .
```

### 运行镜像

```bash
docker run --env-file .env -p 8082:8082 claude-anywhere
```

如果你使用 `uv sync --locked` 构建镜像，记得在依赖变更后同步更新 [`uv.lock`](/D:/Desktop/Claude-Anywhere/uv.lock)。

## 配置说明

### 核心环境变量

- `PREFERRED_PROVIDER`：可选 `openai`、`google`、`anthropic`
- `OPENAI_API_KEY`：OpenAI-compatible 后端必填
- `OPENAI_BASE_URL`：自定义 OpenAI-compatible 接口地址
- `GEMINI_API_KEY`：Gemini API 模式下必填
- `ANTHROPIC_API_KEY`：走 Anthropic 时必填
- `BIG_MODEL`：用于映射 Claude Sonnet 类请求的后端模型
- `SMALL_MODEL`：用于映射 Claude Haiku 类请求的后端模型
- `UNSUPPORTED_THINKING_BEHAVIOR`：非 Anthropic 后端遇到 `thinking` 时的处理策略
- `THINKING_TO_REASONING_EFFORT`：当 `UNSUPPORTED_THINKING_BEHAVIOR=map` 时映射到的 reasoning 等级

### Vertex AI 相关配置

如果你走 Vertex AI 认证模式，可以额外配置：

- `USE_VERTEX_AUTH=true`
- `VERTEX_PROJECT=your-project-id`
- `VERTEX_LOCATION=us-central1`

## 工具兼容性

项目当前已经支持 Claude Code 常见的工具协议转换，包括：

- Anthropic `tool_use`
- Anthropic `tool_result`
- OpenAI 风格的 `tool_calls`
- 多轮工具调用后的继续推理

详细兼容性边界和显式报错策略见：

- [兼容性说明](/D:/Desktop/Claude-Anywhere/docs/compatibility.md)

## 测试

运行当前的协议与兼容性回归测试：

```bash
python -m unittest test_protocol_conversion.py
```

当前测试覆盖包括：

- `tool_result -> tool` 消息转换
- `tool_calls -> tool_use` 响应转换
- 非法 `tool_choice` 显式报错
- `user` 消息错误携带 `tool_use` 显式报错
- OpenAI-compatible 图片输入显式报错
- Gemini 不兼容 tool schema 显式报错
- OpenAI / Gemini / Anthropic adapter 基础路径

## 常见问题

### 1. Claude Code 没有走本地代理

先检查：

- `~/.claude/settings.json` 中是否写了 `ANTHROPIC_BASE_URL`
- 当前终端是否残留了别的 `ANTHROPIC_BASE_URL`
- 本地 `http://localhost:8082/` 是否可访问

### 2. 本地代理启动了，但请求后端时提示 API Key 错误

通常是代理进程启动时没有读到 `.env`，或者环境变量没有带进去。

建议确认：

- 项目根目录下存在 `.env`
- `.env` 中 `OPENAI_API_KEY` 或 `GEMINI_API_KEY` 已正确填写
- 启动命令是在项目根目录下执行的

### 3. Claude Code 能对话，但工具调用不正常

这通常和具体后端平台的 OpenAI-compatible 支持程度有关。即使文本对话正常，不同平台对 function calling 的支持也可能不完全一致。

### 4. 为什么某些后端默认不支持 `thinking`

Anthropic 的 `thinking` 是协议专有能力，不等价于所有其他后端的推理增强参数。为了避免错误映射，项目默认对不支持的后端显式报错。

如果你更希望“尽量继续请求”，可以设置：

```dotenv
UNSUPPORTED_THINKING_BEHAVIOR=drop
```

如果你希望对部分 OpenAI-compatible 后端做近似映射，可以设置：

```dotenv
UNSUPPORTED_THINKING_BEHAVIOR=map
THINKING_TO_REASONING_EFFORT=low
```

### 5. 启动时出现 LiteLLM 拉取 model cost map 失败

如果日志里出现 LiteLLM 无法从 GitHub 拉取 `model_prices_and_context_window.json` 的 warning，通常只是附加元数据获取失败。LiteLLM 会回退到本地备份，这一般不会影响代理主流程。

## 未来蓝图

Claude Anywhere 后续准备继续沿这些方向演进：

### 1. 更细粒度的 provider adapter

当前已经有 adapter 结构，后续会继续按 provider 特性拆分，让不同平台的行为差异更可控。

### 2. 更完整的能力矩阵

目前能力矩阵已覆盖 `thinking`、`top_k`、图片输入和 Gemini schema 规则，后续会继续扩展到：

- 流式 tool call 细节
- 不同后端的 reasoning 参数映射
- 更精细的工具 schema 支持声明

### 3. 更真实的 Claude Code 回归测试

后续会继续增加：

- 多工具并行
- 流式 tool 参数增量输出
- 更贴近 shell / file / search 场景的工具 schema

### 4. 更清晰的兼容性文档

后续会持续更新已验证的平台、模型和已知限制，让使用者在接入前就能快速判断适配风险。

## 适用场景

这个项目比较适合下面这些用法：

- 用 Claude Code 接 OpenAI-compatible 第三方平台
- 用 Claude Code 接自建网关
- 用 Claude Code 接 Gemini
- 在不修改客户端的前提下做协议转换和模型替换

## 贡献

欢迎提 Issue 或 PR，尤其是这些方向：

- 工具调用兼容性
- 不同后端平台的协议适配
- Claude Code 多轮工具场景回归测试
