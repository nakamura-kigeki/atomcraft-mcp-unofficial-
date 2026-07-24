import logging
import os
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    host: str
    port: int
    api_timeout: float
    tree_json_budget: int
    output_base_dir: str


def _get_int(env, key, default, minimum=1):
    raw = env.get(key)
    if raw is None:
        return default
    try:
        value = int(raw)
        if value < minimum:
            raise ValueError
        return value
    except ValueError:
        logger.warning("Invalid %s=%r, falling back to %s", key, raw, default)
        return default


def load(env: dict = None) -> Settings:
    if env is None:
        env = os.environ
    return Settings(
        host=env.get("ATOMCRAFT_HOST", "127.0.0.1"),
        port=_get_int(env, "ATOMCRAFT_PORT", 9000),
        api_timeout=float(_get_int(env, "ATOMCRAFT_API_TIMEOUT", 30)),
        tree_json_budget=_get_int(env, "ATOMCRAFT_TREE_JSON_BUDGET", 50000, minimum=1000),
        output_base_dir=os.path.join(tempfile.gettempdir(), "atomcraft_mcp"),
    )
