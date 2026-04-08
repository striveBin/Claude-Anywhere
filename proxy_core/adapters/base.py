from typing import Any, Dict

from proxy_core.models import MessagesRequest


class ProviderAdapter:
    family = "unknown"

    def prepare_request(self, request: MessagesRequest, litellm_request: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
