import json
import logging
import sys
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import litellm

from proxy_core.compatibility import RequestCompatibilityError, validate_request_compatibility
from proxy_core.config import (
    OPENAI_BASE_URL,
)
from proxy_core.adapters import prepare_backend_request
from proxy_core.conversion import convert_anthropic_to_litellm, convert_litellm_to_anthropic
from proxy_core.models import (
    ContentBlockImage,
    ContentBlockText,
    ContentBlockToolResult,
    ContentBlockToolUse,
    Message,
    MessagesRequest,
    MessagesResponse,
    SystemContent,
    ThinkingConfig,
    TokenCountRequest,
    TokenCountResponse,
    Tool,
    Usage,
)
from proxy_core.streaming import handle_streaming

load_dotenv()

logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)


class MessageFilter(logging.Filter):
    def filter(self, record):
        blocked_phrases = [
            "LiteLLM completion()",
            "HTTP Request:",
            "selected model name for cost calculation",
            "utils.py",
            "cost_calculator",
        ]

        if hasattr(record, "msg") and isinstance(record.msg, str):
            for phrase in blocked_phrases:
                if phrase in record.msg:
                    return False
        return True


class ColorizedFormatter(logging.Formatter):
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record):
        if record.levelno == logging.DEBUG and "MODEL MAPPING" in record.msg:
            return f"{self.BOLD}{self.GREEN}{record.msg}{self.RESET}"
        return super().format(record)


root_logger = logging.getLogger()
root_logger.addFilter(MessageFilter())

for handler in logger.handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.setFormatter(ColorizedFormatter("%(asctime)s - %(levelname)s - %(message)s"))

app = FastAPI()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Request: {request.method} {request.url.path}")
    return await call_next(request)

@app.post("/v1/messages")
async def create_message(request: MessagesRequest, raw_request: Request):
    try:
        validate_request_compatibility(request)

        body = await raw_request.body()
        body_json = json.loads(body.decode("utf-8"))
        original_model = body_json.get("model", "unknown")
        display_model = original_model.split("/")[-1] if "/" in original_model else original_model

        logger.debug(f"PROCESSING REQUEST: Model={request.model}, Stream={request.stream}")
        litellm_request = prepare_backend_request(request)

        num_tools = len(request.tools) if request.tools else 0
        log_request_beautifully(
            "POST",
            raw_request.url.path,
            display_model,
            litellm_request.get("model"),
            len(litellm_request["messages"]),
            num_tools,
            200,
        )

        if request.stream:
            response_generator = await litellm.acompletion(**litellm_request)
            return StreamingResponse(handle_streaming(response_generator, request), media_type="text/event-stream")

        start_time = time.time()
        litellm_response = litellm.completion(**litellm_request)
        logger.debug(f"RESPONSE RECEIVED: Model={litellm_request.get('model')}, Time={time.time() - start_time:.2f}s")
        return convert_litellm_to_anthropic(litellm_response, request)
    except RequestCompatibilityError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        error_details = {"error": str(e), "type": type(e).__name__, "traceback": error_traceback}

        for attr in ["message", "status_code", "response", "llm_provider", "model"]:
            if hasattr(e, attr):
                error_details[attr] = getattr(e, attr)

        if hasattr(e, "__dict__"):
            for key, value in e.__dict__.items():
                if key not in error_details and key not in ["args", "__traceback__"]:
                    error_details[key] = str(value)

        logger.error(f"Error processing request: {json.dumps(sanitize_for_json(error_details), indent=2)}")

        error_message = f"Error: {str(e)}"
        if "message" in error_details and error_details["message"]:
            error_message += f"\nMessage: {error_details['message']}"
        if "response" in error_details and error_details["response"]:
            error_message += f"\nResponse: {error_details['response']}"

        raise HTTPException(status_code=error_details.get("status_code", 500), detail=error_message)


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: TokenCountRequest, raw_request: Request):
    try:
        validate_request_compatibility(
            MessagesRequest(
                model=request.model,
                max_tokens=100,
                messages=request.messages,
                system=request.system,
                tools=request.tools,
                tool_choice=request.tool_choice,
                thinking=request.thinking,
            )
        )

        original_model = request.original_model or request.model
        display_model = original_model.split("/")[-1] if "/" in original_model else original_model

        converted_request = convert_anthropic_to_litellm(
            MessagesRequest(
                model=request.model,
                max_tokens=100,
                messages=request.messages,
                system=request.system,
                tools=request.tools,
                tool_choice=request.tool_choice,
                thinking=request.thinking,
            )
        )

        from litellm import token_counter

        num_tools = len(request.tools) if request.tools else 0
        log_request_beautifully(
            "POST",
            raw_request.url.path,
            display_model,
            converted_request.get("model"),
            len(converted_request["messages"]),
            num_tools,
            200,
        )

        token_counter_args = {"model": converted_request["model"], "messages": converted_request["messages"]}
        if request.model.startswith("openai/") and OPENAI_BASE_URL:
            token_counter_args["api_base"] = OPENAI_BASE_URL

        return TokenCountResponse(input_tokens=token_counter(**token_counter_args))
    except RequestCompatibilityError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except ImportError:
        logger.error("Could not import token_counter from litellm")
        return TokenCountResponse(input_tokens=1000)
    except Exception as e:
        import traceback

        logger.error(f"Error counting tokens: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error counting tokens: {str(e)}")


@app.get("/")
async def root():
    return {"message": "Anthropic Proxy for LiteLLM"}


class Colors:
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return sanitize_for_json(obj.__dict__)
    if hasattr(obj, "text"):
        return str(obj.text)
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def log_request_beautifully(method, path, claude_model, openai_model, num_messages, num_tools, status_code):
    claude_display = f"{Colors.CYAN}{claude_model}{Colors.RESET}"
    endpoint = path.split("?")[0] if "?" in path else path
    openai_display = openai_model.split("/")[-1] if "/" in openai_model else openai_model
    openai_display = f"{Colors.GREEN}{openai_display}{Colors.RESET}"
    tools_str = f"{Colors.MAGENTA}{num_tools} tools{Colors.RESET}"
    messages_str = f"{Colors.BLUE}{num_messages} messages{Colors.RESET}"
    status_str = (
        f"{Colors.GREEN}✓ {status_code} OK{Colors.RESET}"
        if status_code == 200
        else f"{Colors.RED}✗ {status_code}{Colors.RESET}"
    )

    print(f"{Colors.BOLD}{method} {endpoint}{Colors.RESET} {status_str}")
    print(f"{claude_display} → {openai_display} {tools_str} {messages_str}")
    sys.stdout.flush()


if __name__ == "__main__":
    import uvicorn

    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Run with: uvicorn server:app --reload --host 0.0.0.0 --port 8082")
        sys.exit(0)

    uvicorn.run(app, host="0.0.0.0", port=8082, log_level="error")
