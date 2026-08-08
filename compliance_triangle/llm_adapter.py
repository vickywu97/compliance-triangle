"""Live LLM adapter (domestic, OpenAI-compatible).

Lifted from legal-hallucination-bench/scripts/generate_answers.py so the
product can call the same 5 domestic models. API keys come from the
environment (never hardcoded); a model without a key is skipped.

NOTE: this module is only needed for the *live* path. The offline demo
(demo/run_demo.py) uses preset answers and never calls the network, so it runs
with zero dependencies and no API keys.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .config import MODELS

HTTP_TIMEOUT = 180
MAX_RETRIES = 2
RETRY_BACKOFF = 2.0


def _post(url: str, headers: dict, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            last_err = f"HTTP {e.code}: {e.reason} | body={body[:600]}"
            if e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = str(e)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF * (attempt + 1))
    raise RuntimeError(f"request failed after {MAX_RETRIES + 1} attempts: {last_err}")


def _call_openai(cfg: dict, api_key: str, messages: list) -> str:
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {api_key}"}
    payload = {"model": cfg["model"], "messages": messages}
    if not cfg.get("minimal"):
        payload["temperature"] = 0
        payload["stream"] = False
    try:
        obj = _post(cfg["url"], headers, payload)
    except RuntimeError as e:
        if (not cfg.get("minimal")) and "HTTP 400" in str(e):
            obj = _post(cfg["url"], headers,
                        {"model": cfg["model"], "messages": messages})
        else:
            raise
    return obj["choices"][0]["message"]["content"].strip()


def call_model(label: str, messages: list) -> str:
    cfg = next((m for m in MODELS if m["label"] == label), None)
    if cfg is None:
        raise RuntimeError(f"unknown model label: {label}")
    api_key = os.environ.get(cfg["key"], "").strip()
    if not api_key:
        raise RuntimeError(f"missing env var {cfg['key']} for {label}")
    return _call_openai(cfg, api_key, messages)


def available_models() -> list:
    """Labels whose API key is present in the environment."""
    return [m["label"] for m in MODELS
            if os.environ.get(m["key"], "").strip()]
