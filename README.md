# Claude Anywhere

一个将 Anthropic `messages` 协议转换为其他模型后端请求格式的代理服务。

这个项目的目标很直接：让 Claude Code 这类依赖 Anthropic 协议的客户端，可以接入 OpenAI-compatible 接口、Gemini，或者直接接入 Anthropic 本身，而不需要修改客户端调用方式。

它适合这样的场景：

- 你想继续使用 Claude Code
- 你手上的模型并不是 Anthropic 官方模型
- 你有自己的 OpenAI-compatible 网关、第三方平台或模型聚合平台
- 你希望尽量保留 Claude 风格的工具调用流程，而不只是做简单文本转发

## 项目能力

当前项目主要提供这些能力：

- 接收 Anthropic 风格的 `/v1/messages` 请求
- 将 `haiku`、`sonnet` 等 Claude 模型名映射到你配置的后端模型
- 在 Anthropic 风格的 `tool_use` / `tool_result` 与后端 function calling 格式之间做转换
- 支持流式和非流式响应
- 允许 Claude Code 通过一个本地代理访问 OpenAI-compatible、Gemini 或 Anthropic 后端

## 当前状态

这个仓库目前以“手动构建、手动运行”为主。

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
cd claude-code-proxy-main
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

直接代理 Anthropic 示例：

```dotenv
PREFERRED_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-key
```

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
cd D:\Desktop\claude-code-proxy-main
```

#### 2. 准备 `.env`

如果你还没有 `.env`：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，填入你自己的后端配置。例如 OpenAI-compatible 平台：

```dotenv
PREFERRED_PROVIDER=openai

OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1

BIG_MODEL=your-large-model
SMALL_MODEL=your-small-model
```

如果你已经写好了 `.env`，可以跳过这一步。

#### 3. 安装依赖

如果你已经装过，可以跳过。

```powershell
conda create -n claude-proxy python=3.11 -y
conda run -n claude-proxy python -m pip install fastapi[standard] uvicorn httpx pydantic litellm python-dotenv google-auth google-cloud-aiplatform
```

#### 4. 启动服务

```powershell
conda run -n claude-proxy python -m uvicorn server:app --host 0.0.0.0 --port 8082
```

开发模式可以这样启动：

```powershell
conda run -n claude-proxy python -m uvicorn server:app --host 0.0.0.0 --port 8082 --reload
```

#### 5. 验证服务是否启动成功

新开一个 PowerShell 窗口执行：

```powershell
Invoke-WebRequest -Uri http://localhost:8082/ -UseBasicParsing
```

如果启动成功，你应该看到类似返回：

```json
{"message":"Anthropic Proxy for LiteLLM"}
```

#### 6. 让 Claude Code 连接本地代理

方式 A：当前终端临时指定

```powershell
$env:ANTHROPIC_BASE_URL="http://localhost:8082"
$env:ANTHROPIC_API_KEY="dummy-key"
claude
```

方式 B：写入 `C:\Users\WINDOWS\.claude\settings.json`

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8082",
    "ANTHROPIC_API_KEY": "dummy-key"
  },
  "model": "haiku"
}
```

如果你已经在其他终端里设置过别的 `ANTHROPIC_BASE_URL`，建议先清掉，避免混淆：

```powershell
Remove-Item Env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue
```

### 方式二：Linux / macOS

#### 1. 进入项目目录

```bash
cd claude-code-proxy-main
```

#### 2. 准备 `.env`

```bash
cp .env.example .env
```

然后编辑 `.env`。

#### 3. 安装依赖

使用 `uv`：

```bash
uv sync
```

或使用普通 Python 环境：

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

## 常见问题

### 1. Claude Code 没有走本地代理

先检查：

- `~/.claude/settings.json` 中是否写了 `ANTHROPIC_BASE_URL`
- 当前终端是否残留了别的 `ANTHROPIC_BASE_URL`
- 本地 `http://localhost:8082/` 是否可访问

### 2. 本地代理启动了，但请求后端时报 API Key 错误

通常是代理进程启动时没有读到 `.env`，或者环境变量没有带进去。

建议确认：

- 项目根目录下存在 `.env`
- `.env` 中 `OPENAI_API_KEY` 或 `GEMINI_API_KEY` 已正确填写
- 启动命令是在项目根目录下执行的

### 3. Claude Code 能对话，但工具调用不正常

这通常和具体后端平台的 OpenAI-compatible 支持程度有关。即使文本对话正常，不同平台对 function calling 的支持也可能不完全一致。

## 配置说明

### 核心环境变量

- `PREFERRED_PROVIDER`：可选 `openai`、`google`、`anthropic`
- `OPENAI_API_KEY`：OpenAI-compatible 后端必填
- `OPENAI_BASE_URL`：自定义 OpenAI-compatible 接口地址
- `GEMINI_API_KEY`：Gemini API 模式下必填
- `ANTHROPIC_API_KEY`：直接代理 Anthropic 时必填
- `BIG_MODEL`：用于映射 Claude Sonnet 类请求的后端模型
- `SMALL_MODEL`：用于映射 Claude Haiku 类请求的后端模型

### Vertex AI 相关配置

如果你走 Vertex AI 认证模式，可以额外配置：

- `USE_VERTEX_AUTH=true`
- `VERTEX_PROJECT=your-project-id`
- `VERTEX_LOCATION=us-central1`

## 模型映射逻辑

项目会把 Claude 风格的模型请求映射到你实际配置的后端模型。

默认思路是：

- `haiku` -> `SMALL_MODEL`
- `sonnet` -> `BIG_MODEL`

当 `PREFERRED_PROVIDER=openai` 时，会以 `openai/<model>` 的形式发给后端。

当 `PREFERRED_PROVIDER=google` 时，如果识别为 Gemini 模型，会以 `gemini/<model>` 的形式发给后端。

当 `PREFERRED_PROVIDER=anthropic` 时，不再映射到其他厂商，而是直接走 Anthropic。

## 工具调用兼容性

本项目不只是做普通文本转发，也会处理 Claude Code 常见的工具调用协议转换，包括：

- Anthropic 的 `tool_use`
- Anthropic 的 `tool_result`
- OpenAI 风格的 `tool_calls`
- 多轮工具调用后的继续推理

不过需要注意：

- 后端是否真正支持 function calling，取决于具体模型和平台
- 即使是 OpenAI-compatible 接口，不同平台对工具调用字段的兼容程度也可能不同
- 某些 Claude 原生能力，仍然可能需要后续继续做专门适配

## 工作原理

整个流程大致如下：

1. 客户端向 `/v1/messages` 发送 Anthropic 格式请求
2. 代理将请求转换为 LiteLLM 可处理的格式
3. LiteLLM 将请求转发到你选择的后端
4. 后端返回结果后，代理再把响应转换回 Anthropic 兼容格式
5. Claude Code 继续按 Anthropic 协议与代理交互

## 开发说明

- 主要逻辑在 `server.py`
- 基础协议回归测试在 `test_protocol_conversion.py`
- 当前阶段重点是协议兼容和本地可用性，不强调打包分发

## 测试

运行轻量协议测试：

```bash
python -m unittest test_protocol_conversion.py
```

## 已知限制

- 兼容性会受到目标平台对 OpenAI 或 Gemini 协议实现质量的影响
- **某些 Claude Code 工具场景仍可能需要继续补适配**

## 适用场景

这个项目比较适合下面这些用法：

- 用 Claude Code 接 OpenAI-compatible 第三方平台
- 用 Claude Code 接自建网关
- 用 Claude Code 接 Gemini
- 在不修改客户端的前提下做协议转换和模型替换

## 贡献

欢迎提 Issue 或 PR，尤其是这几个方向：

- 工具调用兼容性
- 不同后端平台的协议适配
- Claude Code 多轮工具场景回归测试
