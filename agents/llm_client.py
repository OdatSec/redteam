"""Minimal Ollama chat client for the v0.2 LLM victim.

Talks to a locally-running Ollama server (`ollama serve`) over HTTP using only
the Python standard library -- no extra dependencies. Requests JSON-mode output
at temperature 0 with a fixed seed so runs are as reproducible as a local LLM
allows.

This client performs NO safety filtering. It is deliberately a thin transport so
the LLM victim remains a vulnerable baseline (v0.2 scope: no defense).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class LLMResponse:
    ok: bool
    content: str            # raw text returned by the model
    latency_s: float        # wall-clock inference time
    error: str = ""


class OllamaClient:
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        temperature: float = 0.0,
        seed: int = 42,
        timeout_s: float = 120.0,
        json_mode: bool = True,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.seed = seed
        self.timeout_s = timeout_s
        self.json_mode = json_mode

    def chat(self, system: str, user: str) -> LLMResponse:
        """Single-turn chat. Returns raw model content (expected to be JSON)."""
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": self.temperature, "seed": self.seed},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.json_mode:
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=data,
            headers={"Content-Type": "application/json"},
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body.get("message", {}).get("content", "")
            return LLMResponse(ok=True, content=content, latency_s=time.time() - t0)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            return LLMResponse(ok=False, content="", latency_s=time.time() - t0,
                               error=str(err))

    def health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False
