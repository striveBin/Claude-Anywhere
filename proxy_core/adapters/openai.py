from typing import Any, Dict

from proxy_core.adapters.base import ProviderAdapter
from proxy_core.config import OPENAI_API_KEY, OPENAI_BASE_URL
from proxy_core.providers import normalize_openai_messages


class OpenAIAdapter(ProviderAdapter):
    family = "openai"

    def prepare_request(self, request, litellm_request: Dict[str, Any]) -> Dict[str, Any]:
        litellm_request["api_key"] = OPENAI_API_KEY
        if OPENAI_BASE_URL:
            litellm_request["api_base"] = OPENAI_BASE_URL
        normalize_openai_messages(litellm_request)
        return litellm_request
