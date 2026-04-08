from typing import Any, Dict

from proxy_core.adapters.base import ProviderAdapter
from proxy_core.config import GEMINI_API_KEY, USE_VERTEX_AUTH, VERTEX_LOCATION, VERTEX_PROJECT


class GeminiAdapter(ProviderAdapter):
    family = "gemini"

    def prepare_request(self, request, litellm_request: Dict[str, Any]) -> Dict[str, Any]:
        if USE_VERTEX_AUTH:
            litellm_request["vertex_project"] = VERTEX_PROJECT
            litellm_request["vertex_location"] = VERTEX_LOCATION
            litellm_request["custom_llm_provider"] = "vertex_ai"
        else:
            litellm_request["api_key"] = GEMINI_API_KEY
        return litellm_request
