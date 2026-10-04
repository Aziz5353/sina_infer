import os

from dotenv import load_dotenv


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    def __init__(self):
        load_dotenv()
        self.OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
        self.OPENAI_BASE_URL = os.environ["OPENAI_BASE_URL"]
        self.ANALYZER_MODEL = os.environ["ANALYZER_MODEL"]
        self.CONTEXTUALIZE_MODEL = os.environ["CONTEXTUALIZE_MODEL"]
        self.CONTEXTUALIZE_HISTORY_TURNS = int(os.environ.get("CONTEXTUALIZE_HISTORY_TURNS", "6"))
        self.ASSESS_MODEL = os.environ["ASSESS_MODEL"]
        self.GENERATE_MODEL = os.environ["GENERATE_MODEL"]
        self.GENERATE_TEMPERATURE = float(os.environ.get("GENERATE_TEMPERATURE", "0.1"))
        self.CLARIFY_MODEL = os.environ["CLARIFY_MODEL"]
        self.REFUSE_MODEL = os.environ["REFUSE_MODEL"]
        self.TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.LOG_TO_FILE = os.environ.get("LOG_TO_FILE", "false").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        # CORS
        self.CORS_ALLOWED_ORIGINS = _csv(
            os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:4200")
        )

        # Search Settings
        # Sina never searches outside this whitelist, so an empty list is fatal.
        self.SEARCH_ALLOWED_DOMAINS = _csv(os.environ.get("SEARCH_ALLOWED_DOMAINS", ""))
        if not self.SEARCH_ALLOWED_DOMAINS:
            raise ValueError(
                "SEARCH_ALLOWED_DOMAINS must list at least one domain "
                "(comma-separated); Sina does not search the open web."
            )
        self.SEARCH_MAX_RESULTS = int(os.environ.get("SEARCH_MAX_RESULTS", "5"))
        self.SEARCH_MIN_RESULTS = int(os.environ.get("SEARCH_MIN_RESULTS", "2"))
        self.SEARCH_QUERIES_PER_TURN = int(os.environ.get("SEARCH_QUERIES_PER_TURN", "3"))
        self.MAX_SEARCH_ATTEMPTS = int(os.environ.get("MAX_SEARCH_ATTEMPTS", "2"))

        # Clarify Settings
        self.MAX_CLARIFYING_QUESTIONS = int(os.environ.get("MAX_CLARIFYING_QUESTIONS", "4"))

    _SECRET_KEYS = frozenset({"OPENAI_API_KEY", "TAVILY_API_KEY"})

    def as_log_dict(self) -> dict:
        """Return all settings as a dict, with secret values redacted."""
        return {
            key: ("***REDACTED***" if key in self._SECRET_KEYS else value)
            for key, value in sorted(vars(self).items())
        }


settings = Settings()
