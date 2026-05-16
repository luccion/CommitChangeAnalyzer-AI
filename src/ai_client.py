from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib import error, request


@dataclass(slots=True)
class ApiConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float
    timeout_seconds: int


def load_api_config(repo_root: Path) -> ApiConfig:
    env_values = _load_dotenv(repo_root / ".env")

    def resolve(name: str, fallback: str | None = None) -> str | None:
        if name in os.environ:
            return os.environ[name]
        if name in env_values:
            return env_values[name]
        return fallback

    api_key = resolve("AI_API_KEY") or resolve("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("API mode requires AI_API_KEY or OPENAI_API_KEY in .env or the environment.")

    base_url = (resolve("AI_BASE_URL") or resolve("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = resolve("AI_MODEL") or resolve("OPENAI_MODEL") or "gpt-4.1-mini"
    temperature_text = resolve("AI_TEMPERATURE") or "0.2"
    timeout_text = resolve("AI_TIMEOUT_SECONDS") or "120"

    try:
        temperature = float(temperature_text)
    except ValueError as error_value:
        raise RuntimeError(f"Invalid AI_TEMPERATURE value: {temperature_text}") from error_value
    try:
        timeout_seconds = int(timeout_text)
    except ValueError as error_value:
        raise RuntimeError(f"Invalid AI_TIMEOUT_SECONDS value: {timeout_text}") from error_value

    return ApiConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
    )


def run_remote_analysis(
    config: ApiConfig,
    *,
    prompt_text: str,
    diff_markdown: str,
    diff_json_text: str,
    summary_text: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.model,
        "temperature": config.temperature,
        "messages": [
            {
                "role": "system",
                "content": prompt_text,
            },
            {
                "role": "user",
                "content": (
                    "请基于以下材料完成分析。\n\n"
                    "【客观摘要】\n"
                    f"{summary_text}\n\n"
                    "【Diff Markdown】\n"
                    f"{diff_markdown}\n\n"
                    "【Diff JSON】\n"
                    f"{diff_json_text}"
                ),
            },
        ],
        "response_format": {"type": "text"},
    }

    response_payload = _post_json(
        url=f"{config.base_url}/chat/completions",
        api_key=config.api_key,
        payload=payload,
        timeout_seconds=config.timeout_seconds,
    )
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Remote AI response does not contain choices.")
    first_choice = cast(dict[str, Any], choices[0])
    message = cast(dict[str, Any] | None, first_choice.get("message"))
    if not isinstance(message, dict):
        raise RuntimeError("Remote AI response message is missing.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Remote AI response content is empty.")
    return {
        "model": config.model,
        "base_url": config.base_url,
        "content": content.strip(),
        "raw_response": response_payload,
    }


def _load_dotenv(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _post_json(url: str, api_key: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as http_error:
        body = http_error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Remote AI request failed with HTTP {http_error.code}: {body}") from http_error
    except error.URLError as url_error:
        raise RuntimeError(f"Remote AI request failed: {url_error.reason}") from url_error

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as decode_error:
        raise RuntimeError("Remote AI response is not valid JSON.") from decode_error
    if not isinstance(decoded, dict):
        raise RuntimeError("Remote AI response root must be a JSON object.")
    return cast(dict[str, Any], decoded)