from django.conf import settings

from apps.core.services import UniversalQueryProcessor


class UCEAIService:
    def __init__(self):
        self.enabled = bool(getattr(settings, "AI_ENABLED", False))
        self.client = None
        if self.enabled:
            from anthropic import Anthropic

            self.client = Anthropic(api_key=getattr(settings, "ANTHROPIC_API_KEY", None))

    def parse_natural_language_query(self, nl_input, available_modules):
        if not self.enabled:
            return self._keyword_fallback(nl_input, available_modules)
        # Keep the core deterministic; AI output is an enhancement and must be validated by callers.
        return self._keyword_fallback(nl_input, available_modules)

    def generate_insight(self, data):
        if not self.enabled:
            return None
        return None

    def predict_anomaly(self, module, entity_id):
        if not self.enabled:
            return None
        return None

    def _keyword_fallback(self, nl_input, available_modules):
        processor = UniversalQueryProcessor()
        iql = processor.normalize(nl_input, "nl", available_modules)
        return iql

