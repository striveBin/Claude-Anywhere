import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "unset")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "unset")
USE_VERTEX_AUTH = os.environ.get("USE_VERTEX_AUTH", "False").lower() == "true"

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")
PREFERRED_PROVIDER = os.environ.get("PREFERRED_PROVIDER", "openai").lower()
UNSUPPORTED_THINKING_BEHAVIOR = os.environ.get("UNSUPPORTED_THINKING_BEHAVIOR", "error").lower()

BIG_MODEL = os.environ.get("BIG_MODEL", "gpt-4.1")
SMALL_MODEL = os.environ.get("SMALL_MODEL", "gpt-4.1-mini")

OPENAI_MODELS = [
    "o3-mini",
    "o1",
    "o1-mini",
    "o1-pro",
    "gpt-4.5-preview",
    "gpt-4o",
    "gpt-4o-audio-preview",
    "chatgpt-4o-latest",
    "gpt-4o-mini",
    "gpt-4o-mini-audio-preview",
    "gpt-4.1",
    "gpt-4.1-mini",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]
