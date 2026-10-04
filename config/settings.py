import os

from dotenv import load_dotenv


class Settings:
    def __init__(self):
        load_dotenv()
        self.OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
        self.OPENAI_BASE_URL = os.environ["OPENAI_BASE_URL"]
        self.ANALYZER_MODEL = os.environ["ANALYZER_MODEL"]
        self.CONTEXTUALIZE_MODEL = os.environ["CONTEXTUALIZE_MODEL"]
        self.CONTEXTUALIZE_HISTORY_TURNS = int(os.environ.get("CONTEXTUALIZE_HISTORY_TURNS", "6"))
        self.GENERATE_MODEL = os.environ["GENERATE_MODEL"]
        self.GENERATE_TEMPERATURE = float(os.environ.get("GENERATE_TEMPERATURE", "0.2"))
        self.REFUSE_MODEL = os.environ["REFUSE_MODEL"]
        self.HF_EMBEDDING_MODEL_NAME = os.environ.get("HF_EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
        self.HF_EMBEDDING_DEVICE = os.environ.get("HF_EMBEDDING_DEVICE", "cpu")
        self.TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]
        self.PGVECTOR_CONNECTION = os.environ["PGVECTOR_CONNECTION"]
        self.PGVECTOR_COLLECTION = os.environ["PGVECTOR_COLLECTION"]
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
        self.LOG_TO_FILE = os.environ.get("LOG_TO_FILE", "false").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        # CORS
        self.CORS_ALLOWED_ORIGINS = [
            o.strip()
            for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:4200").split(",")
            if o.strip()
        ]

        # Search Settings
        self.SEARCH_MAX_RESULTS = int(os.environ.get("SEARCH_MAX_RESULTS", "5"))
        self.SEARCH_ALLOWED_DOMAINS = [
            d.strip()
            for d in os.environ.get("SEARCH_ALLOWED_DOMAINS", "shamela.ws").split(",")
            if d.strip()
        ]
        self.SEARCH_MIN_RESULTS = int(os.environ.get("SEARCH_MIN_RESULTS", "2"))
        self.SEARCH_MIN_TOP_SCORE = float(os.environ.get("SEARCH_MIN_TOP_SCORE", "0.50"))

        # Retrieval Settings
        self.RETRIEVAL_SCORE_THRESHOLD = float(os.environ.get("RETRIEVAL_SCORE_THRESHOLD", "0.60"))
        self.TOP_K_RETRIEVAL = int(os.environ.get("TOP_K_RETRIEVAL", "8"))

    _SECRET_KEYS = frozenset(
        {"OPENAI_API_KEY", "TAVILY_API_KEY", "PGVECTOR_CONNECTION"}
    )

    def as_log_dict(self) -> dict:
        """Return all settings as a dict, with secret values redacted."""
        return {
            key: ("***REDACTED***" if key in self._SECRET_KEYS else value)
            for key, value in sorted(vars(self).items())
        }


settings = Settings()
