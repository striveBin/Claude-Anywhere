import logging
from typing import Dict

from proxy_core.adapters.anthropic import AnthropicAdapter
from proxy_core.adapters.base import ProviderAdapter
from proxy_core.adapters.gemini import GeminiAdapter
from proxy_core.adapters.openai import OpenAIAdapter
from proxy_core.capabilities import get_backend_family
from proxy_core.conversion import convert_anthropic_to_litellm
from proxy_core.models import MessagesRequest

logger = logging.getLogger(__name__)

ADAPTERS: Dict[str, ProviderAdapter] = {
    "openai": OpenAIAdapter(),
    "gemini": GeminiAdapter(),
    "anthropic": AnthropicAdapter(),
}


def prepare_backend_request(request: MessagesRequest) -> dict:
    litellm_request = convert_anthropic_to_litellm(request)
    family = get_backend_family(request.model)
    adapter = ADAPTERS.get(family)
    if not adapter:
        logger.warning(f"No adapter registered for backend family '{family}', returning base LiteLLM request.")
        return litellm_request
    return adapter.prepare_request(request, litellm_request)
