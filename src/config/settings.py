import json
import os

from dotenv import load_dotenv


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self):
        load_dotenv()
        self.OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
        self.OPENAI_BASE_URL = os.environ["OPENAI_BASE_URL"]
        self.PLAN_MODEL = os.environ["PLAN_MODEL"]
        self.ANSWER_MODEL = os.environ["ANSWER_MODEL"]
        self.ANSWER_TEMPERATURE = float(os.environ.get("ANSWER_TEMPERATURE", "0.1"))
        # vLLM only: OpenAI rejects the `chat_template_kwargs` this sends.
        self.DISABLE_THINKING = _bool(os.environ.get("DISABLE_THINKING", "false"))
        self.HISTORY_TURNS = int(os.environ.get("HISTORY_TURNS", "6"))
        self.TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.LOG_TO_FILE = _bool(os.environ.get("LOG_TO_FILE", "false"))

        self.SAVE_CONVERSATIONS = _bool(os.environ.get("SAVE_CONVERSATIONS", "false"))
        # Only used to name the conversations file, e.g. data/conversations_gpt-5.1.csv
        generation_model_name = os.environ.get("GENERATION_MODEL_NAME", "").strip()
        default_csv_name = (
            f"conversations_{generation_model_name}.csv" if generation_model_name else "conversations.csv"
        )
        self.CONVERSATIONS_CSV_PATH = os.environ.get(
            "CONVERSATIONS_CSV_PATH", f"data/{default_csv_name}"
        )

        # CORS
        self.CORS_ALLOWED_ORIGINS = _csv(
            os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:4200")
        )

        # Search Settings
        # Sina never searches outside this whitelist, so an empty list is fatal.
        self.SEARCH_ALLOWED_DOMAINS = json.loads(os.environ.get("SEARCH_ALLOWED_DOMAINS", "[]"))
        if not self.SEARCH_ALLOWED_DOMAINS:
            raise ValueError(
                "SEARCH_ALLOWED_DOMAINS must list at least one domain "
                "(as a JSON list); Sina does not search the open web."
            )
        self.SEARCH_MAX_RESULTS = int(os.environ.get("SEARCH_MAX_RESULTS", "5"))
        self.SEARCH_QUERIES_PER_TURN = int(os.environ.get("SEARCH_QUERIES_PER_TURN", "3"))
        self.SEARCH_MAX_SOURCES = int(os.environ.get("SEARCH_MAX_SOURCES", "10"))
        self.SEARCH_EXTRACT_TOP_K = int(os.environ.get("SEARCH_EXTRACT_TOP_K", "4"))
        self.SEARCH_EXTRACT_MAX_CHARS = int(os.environ.get("SEARCH_EXTRACT_MAX_CHARS", "3000"))

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
