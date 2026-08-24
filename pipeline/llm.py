"""
Shared LLM wrapper. All nodes call llm_call() — never the provider client directly.
Guarantees: temperature=0, structured logging, exponential backoff on rate limits.

Provider selection (automatic, based on .env):
  ANTHROPIC_API_KEY set                    → Anthropic (Claude models, highest priority)
  LLM_API_KEY + LLM_BASE_URL set          → Any OpenAI-compatible provider (Groq, Gemini, Ollama…)
  OPENAI_API_KEY set                       → OpenAI (fallback)

Quick-start examples (.env):
  # Groq (free, no CC — https://console.groq.com)
  LLM_API_KEY=gsk_...
  LLM_BASE_URL=https://api.groq.com/openai/v1
  LLM_CHEAP_MODEL=llama-3.3-70b-versatile
  LLM_STRONG_MODEL=llama-3.3-70b-versatile

  # Google Gemini (free, no CC — https://aistudio.google.com)
  LLM_API_KEY=AIza...
  LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
  LLM_CHEAP_MODEL=gemini-2.0-flash
  LLM_STRONG_MODEL=gemini-2.0-flash

  # Ollama (local, unlimited — https://ollama.com)
  LLM_API_KEY=ollama
  LLM_BASE_URL=http://localhost:11434/v1
  LLM_CHEAP_MODEL=llama3.1
  LLM_STRONG_MODEL=llama3.1

  # Anthropic (Claude — https://console.anthropic.com)
  ANTHROPIC_API_KEY=sk-ant-...
"""

import json
import os
import pathlib
import re
import time

from jinja2 import Environment, FileSystemLoader

_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
_jinja_env: Environment | None = None

# Default Claude→GPT name mapping when falling back to plain OpenAI
_OPENAI_MODEL_MAP: dict[str, str] = {
    "claude-haiku-4-5-20251001": "gpt-4o-mini",
    "claude-haiku-4-5":          "gpt-4o-mini",
    "claude-sonnet-4-6":         "gpt-4o",
    "claude-sonnet-4-5":         "gpt-4o",
    "claude-opus-4-8":           "gpt-4o",
}


def _provider() -> str:
    """Return 'anthropic', 'compat', or 'openai'."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL"):
        return "compat"    # any OpenAI-compatible provider
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    raise EnvironmentError(
        "No LLM API key configured. Add one of the following to .env:\n"
        "  ANTHROPIC_API_KEY=...           (Anthropic Claude)\n"
        "  LLM_API_KEY=... + LLM_BASE_URL= (Groq / Gemini / Ollama)\n"
        "  OPENAI_API_KEY=...              (OpenAI)\n"
        "See pipeline/llm.py header for quick-start examples."
    )


def _resolve_model(model: str) -> str:
    """
    Resolve the model name for the active provider.
    - Anthropic: use as-is (Claude model ID).
    - compat: use LLM_CHEAP_MODEL / LLM_STRONG_MODEL env vars if set,
              otherwise fall back to the compat default.
    - openai: map Claude names → GPT equivalents.
    """
    provider = _provider()
    if provider == "anthropic":
        return model

    if provider == "compat":
        # The caller passes Claude model names; map them to configured models.
        cheap_names = {"claude-haiku-4-5-20251001", "claude-haiku-4-5"}
        env_model = (
            os.environ.get("LLM_CHEAP_MODEL")
            if model in cheap_names
            else os.environ.get("LLM_STRONG_MODEL")
        )
        return env_model or "llama-3.3-70b-versatile"

    # openai
    return _OPENAI_MODEL_MAP.get(model, "gpt-4o-mini")


def _maybe_wrap(client, kind: str):
    """Wrap an SDK client with LangSmith tracing when LANGSMITH_TRACING is on, so
    each LLM call appears in the trace (prompt, response, tokens) nested under its
    node. Returns the raw client unchanged if tracing is off or langsmith is
    unavailable — never raises. `kind` is 'anthropic' or 'openai'."""
    if os.environ.get("LANGSMITH_TRACING", "").strip().lower() not in ("1", "true", "yes"):
        return client
    try:
        from langsmith.wrappers import wrap_anthropic, wrap_openai
        return wrap_anthropic(client) if kind == "anthropic" else wrap_openai(client)
    except Exception:
        return client


def _is_daily_rate_limit(exc: Exception) -> bool:
    """A rate limit that names a *daily* token quota (e.g. 'tokens per day (TPD)').
    Retrying within a run is futile — surface it immediately."""
    msg = str(exc).lower()
    return ("per day" in msg) or ("tpd" in msg) or ("tokens per day" in msg)


def resolve_temperature(temperature: float | None = None) -> float:
    """
    Resolve the sampling temperature (Constitution IV, amended v1.1.0).
    Precedence: explicit arg → LLM_TEMPERATURE env → 0.7 default.
    """
    if temperature is not None:
        return float(temperature)
    env = os.environ.get("LLM_TEMPERATURE")
    if env is not None and env.strip() != "":
        try:
            return float(env)
        except ValueError:
            pass
    return 0.7


def _get_jinja(prompts_dir: str) -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _jinja_env


def render_prompt(template_name: str, prompts_dir: str | None = None, **kwargs) -> str:
    """Render a Jinja2 template from the prompts directory."""
    if prompts_dir is None:
        prompts_dir = str(_PROJECT_ROOT / "prompts")
    env = _get_jinja(prompts_dir)
    tmpl = env.get_template(template_name)
    return tmpl.render(**kwargs)


def extract_json(text: str) -> dict | list:
    """Parse JSON from an LLM response, stripping markdown fences if present."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def extract_code_block(text: str, lang: str = "") -> str:
    """Extract content from a fenced code block; return text as-is if no fences found."""
    pattern = rf"```{re.escape(lang)}\s*\n(.*?)\n?```"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    text = re.sub(r"^```\w*\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def llm_call(
    *,
    node: str,
    model: str,
    prompt: str,
    run_id: str,
    max_tokens: int = 4096,
    max_retries: int = 3,
    temperature: float | None = None,
) -> tuple[str, dict]:
    """
    Call the active LLM provider and return (response_text, log_entry).
    log_entry matches the llm_calls schema in GraphState.

    temperature: configurable per Constitution IV (v1.1.0). None → LLM_TEMPERATURE
    env → 0.7. The resolved value is applied to the call and recorded in the log.
    """
    provider = _provider()
    resolved = _resolve_model(model)
    temp = resolve_temperature(temperature)
    log: dict = {
        "node": node,
        "model": resolved,
        "provider": provider,
        "run_id": run_id,
        "temperature": temp,
        "tokens_in": 0,
        "tokens_out": 0,
        "latency_ms": 0,
        "rate_limit_retries": 0,
    }

    if provider == "anthropic":
        return _call_anthropic(resolved, prompt, max_tokens, max_retries, log, temp)
    else:
        # Both "compat" and "openai" use the OpenAI client
        base_url = os.environ.get("LLM_BASE_URL")      # None → default OpenAI URL
        api_key = (
            os.environ.get("LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        return _call_openai_compat(resolved, prompt, max_tokens, max_retries, log,
                                   api_key=api_key, base_url=base_url, temperature=temp)


# ── Anthropic ────────────────────────────────────────────────────────────────

def _call_anthropic(
    model: str, prompt: str, max_tokens: int, max_retries: int, log: dict,
    temperature: float,
) -> tuple[str, dict]:
    import anthropic

    client = _maybe_wrap(
        anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]), "anthropic"
    )
    for attempt in range(max_retries):
        t0 = time.monotonic()
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            log["tokens_in"] = response.usage.input_tokens
            log["tokens_out"] = response.usage.output_tokens
            log["latency_ms"] = int((time.monotonic() - t0) * 1000)
            return response.content[0].text, log

        except anthropic.RateLimitError as e:
            if _is_daily_rate_limit(e):
                raise  # daily quota — retrying won't help
            log["rate_limit_retries"] += 1
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("_call_anthropic: unreachable")


# ── OpenAI-compatible (OpenAI, Groq, Gemini, Ollama, …) ─────────────────────

def _call_openai_compat(
    model: str,
    prompt: str,
    max_tokens: int,
    max_retries: int,
    log: dict,
    api_key: str | None,
    base_url: str | None,
    temperature: float,
) -> tuple[str, dict]:
    from openai import OpenAI, RateLimitError

    kwargs: dict = {"api_key": api_key or "no-key"}
    if base_url:
        kwargs["base_url"] = base_url

    client = _maybe_wrap(OpenAI(**kwargs), "openai")

    for attempt in range(max_retries):
        t0 = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            log["tokens_in"] = response.usage.prompt_tokens
            log["tokens_out"] = response.usage.completion_tokens
            log["latency_ms"] = int((time.monotonic() - t0) * 1000)
            return response.choices[0].message.content, log

        except RateLimitError as e:
            if _is_daily_rate_limit(e):
                raise  # daily quota — retrying won't help
            log["rate_limit_retries"] += 1
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("_call_openai_compat: unreachable")
