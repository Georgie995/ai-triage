"""Settings from ai-triage.toml (optional; git-ignored). The API key is never a setting: it
comes only from the environment variable ANTHROPIC_API_KEY."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULTS = {
    "model": "claude-haiku-5-5",
    "effort": "medium",                 # Haiku 5.5's default; a setting to measure, not guess
    "timeout_seconds": 60,
    # Anthropic's published Haiku 5.5 prices (USD per million tokens, prompts up to 100K tokens),
    # as cached 2026-10-06. Configurable because prices change.
    "price_input_per_mtok_usd": 0.10,
    "price_output_per_mtok_usd": 0.50,
    "max_run_cost_usd": 0.30,           # about £0.25: the harness stops before a run estimated above this
    "playbook": str(ROOT / "playbook.toml"),
}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}


class SettingsError(Exception):
    """The settings can't be used (exit code 3)."""


def load_settings(path=None):
    settings = dict(DEFAULTS)
    if path is not None and Path(path).exists():
        try:
            data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise SettingsError(f"{path} is not valid TOML: {error}") from error
        unknown = set(data) - set(DEFAULTS)
        if unknown:
            raise SettingsError(f"{path}: unknown setting(s): {', '.join(sorted(unknown))}")
        settings.update(data)
    if settings["effort"] not in EFFORTS:
        raise SettingsError(f"effort must be one of {sorted(EFFORTS)}")
    return settings


def cost_usd(usage, settings):
    return (usage["input_tokens"] / 1e6 * settings["price_input_per_mtok_usd"]
            + usage["output_tokens"] / 1e6 * settings["price_output_per_mtok_usd"])
