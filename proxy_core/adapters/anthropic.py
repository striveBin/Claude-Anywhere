from typing import Any, Dict

from proxy_core.adapters.base import ProviderAdapter
from proxy_core.config import ANTHROPIC_API_KEY


class AnthropicAdapter(ProviderAdapter):
    family = "anthropic"

    def prepare_request(self, request, litellm_request: Dict[str, Any]) -> Dict[str, Any]:
        litellm_request["api_key"] = ANTHROPIC_API_KEY
        return litellm_request
