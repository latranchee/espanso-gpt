#!/usr/bin/env python3
"""
LLM Client Abstraction Module

Provides a unified interface for chat completions across multiple providers
(OpenAI and Anthropic). Provider is auto-detected from model name prefix.
"""
import os
import re
import sys
import time
from typing import Any

from dotenv import load_dotenv

import logger

# Load environment variables from .env in the scripts directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# API keys live in the shush vault; its localhost proxy strips client credential
# headers and injects the real key, so the SDKs only need a non-empty placeholder.
SHUSH_PROXY_URL = os.getenv("SHUSH_PROXY_URL", "http://127.0.0.1:8765").rstrip("/")
SHUSH_PLACEHOLDER_KEY = "injected-by-shush-proxy"
SHUSH_OPENAI_PROVIDER = "openai_espanso"

# These older Claude models still take temperature; newer ones reject it with a 400.
SAMPLING_PARAM_MODEL_PREFIXES = ("claude-3", "claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4-5")
REFUSAL_FALLBACK_MODEL_PREFIXES = ("claude-opus-5", "claude-fable")
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Newer models think by default and max_tokens caps thinking plus the answer.
THINKING_MIN_MAX_TOKENS = 16000
THINKING_EFFORT = "low"
# OpenAI reasoning models reject temperature unless reasoning_effort is "none".
OPENAI_REASONING_MODEL_PREFIXES = ("gpt-5", "gpt-6", "o1", "o3", "o4")

# Lazy-loaded clients to avoid import errors if one SDK is missing
_openai_client = None
_anthropic_client = None


def _get_openai_client():
    """Lazily initialize and return the OpenAI client (routed through shush)."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(
            base_url=f"{SHUSH_PROXY_URL}/{SHUSH_OPENAI_PROVIDER}/v1", api_key=SHUSH_PLACEHOLDER_KEY
        )
    return _openai_client


def _get_anthropic_client():
    """Lazily initialize and return the Anthropic client (routed through shush)."""
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(base_url=f"{SHUSH_PROXY_URL}/anthropic", api_key=SHUSH_PLACEHOLDER_KEY)
    return _anthropic_client


def _detect_provider(model: str) -> str:
    """Detect the provider from the model name."""
    if model.startswith("claude"):
        return "anthropic"
    elif model.startswith("gpt") or model.startswith("o1"):
        return "openai"
    else:
        raise ValueError(f"Unknown model provider for model: {model}")


def _extract_system_message(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """
    Extract system message from messages list.
    Returns (system_message, remaining_messages).
    """
    system_content = None
    filtered_messages = []

    for msg in messages:
        if msg.get("role") == "system":
            system_content = msg.get("content", "")
        else:
            filtered_messages.append(msg)

    return system_content, filtered_messages


def _convert_openai_image_to_anthropic(content: list[dict]) -> list[dict]:
    """
    Convert OpenAI-style image content to Anthropic format.

    OpenAI: {"type": "image_url", "image_url": {"url": "data:mime;base64,DATA"}}
    Anthropic: {"type": "image", "source": {"type": "base64", "media_type": "mime", "data": "DATA"}}
    """
    converted = []
    for item in content:
        if item.get("type") == "image_url":
            url = item.get("image_url", {}).get("url", "")
            # Parse data URL: data:image/png;base64,ACTUALDATA
            match = re.match(r"data:([^;]+);base64,(.+)", url)
            if match:
                media_type = match.group(1)
                data = match.group(2)
                converted.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data
                    }
                })
            else:
                # URL-based image (not base64) - pass as-is for now
                converted.append(item)
        elif item.get("type") == "text":
            converted.append(item)
        else:
            converted.append(item)

    return converted


def _convert_messages_for_anthropic(messages: list[dict]) -> list[dict]:
    """Convert messages to Anthropic format, handling image content."""
    converted = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            # Multi-part content (text + images)
            converted.append({
                "role": msg["role"],
                "content": _convert_openai_image_to_anthropic(content)
            })
        else:
            converted.append(msg)
    return converted


def _call_openai(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str | None = None
) -> str:
    """Make an OpenAI API call."""
    client = _get_openai_client()
    api_args = _build_openai_args(model, messages, temperature, max_tokens, reasoning_effort)
    response = client.chat.completions.create(**api_args)
    return response.choices[0].message.content.strip()


def _build_openai_args(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str | None = None
) -> dict[str, Any]:
    """Build request arguments matching what the target OpenAI model accepts."""
    api_args: dict[str, Any] = {"model": model, "messages": messages}

    if model.startswith(OPENAI_REASONING_MODEL_PREFIXES):
        effort = reasoning_effort or THINKING_EFFORT
        api_args["max_completion_tokens"] = max(max_tokens, THINKING_MIN_MAX_TOKENS)
        api_args["reasoning_effort"] = effort
        if effort == "none":
            api_args["temperature"] = temperature
    else:
        api_args["max_completion_tokens"] = max_tokens
        api_args["temperature"] = temperature

    return api_args


def _call_anthropic(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    system_message: str | None
) -> str:
    """Make an Anthropic API call."""
    client = _get_anthropic_client()

    # Extract system message if not provided separately
    if system_message is None:
        system_message, messages = _extract_system_message(messages)

    api_args = _build_anthropic_args(
        model, _convert_messages_for_anthropic(messages), temperature, max_tokens, system_message
    )
    response = client.beta.messages.create(**api_args)
    return _extract_anthropic_text(response)


def _build_anthropic_args(
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    system_message: str | None
) -> dict[str, Any]:
    """Build request arguments matching what the target Claude model accepts."""
    api_args: dict[str, Any] = {"model": model, "messages": messages}

    if model.startswith(SAMPLING_PARAM_MODEL_PREFIXES):
        api_args["temperature"] = temperature
        api_args["max_tokens"] = max_tokens
    else:
        api_args["max_tokens"] = max(max_tokens, THINKING_MIN_MAX_TOKENS)
        api_args["output_config"] = {"effort": THINKING_EFFORT}

    if model.startswith(REFUSAL_FALLBACK_MODEL_PREFIXES):
        api_args["betas"] = [REFUSAL_FALLBACK_BETA]
        api_args["extra_body"] = {"fallbacks": "default"}

    if system_message:
        api_args["system"] = system_message

    return api_args


def _extract_anthropic_text(response: Any) -> str:
    """Return the visible text, skipping thinking/fallback blocks; raise on refusal."""
    if response.stop_reason == "refusal":
        category = getattr(getattr(response, "stop_details", None), "category", None)
        raise RuntimeError(f"Claude declined the request (category: {category})")
    return "".join(block.text for block in response.content if block.type == "text").strip()


def create_chat_completion(
    model: str,
    messages: list[dict],
    temperature: float = 0.6,
    max_tokens: int = 2000,
    system_message: str | None = None,
    reasoning_effort: str | None = None
) -> str:
    """
    Create a chat completion using the appropriate provider.

    Provider is auto-detected from model name:
    - claude-* -> Anthropic
    - gpt-*, o1-* -> OpenAI

    Args:
        model: The model identifier (e.g., "claude-opus-5", "gpt-4o-mini")
        messages: List of message dicts with "role" and "content" keys.
                  For images, use OpenAI format - will be converted for Anthropic.
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens in response
        system_message: Optional system message (for Anthropic, passed separately)
        reasoning_effort: OpenAI reasoning effort override; "none" re-enables temperature

    Returns:
        The assistant's response text.

    Raises:
        ValueError: If provider cannot be detected or API key is missing.
    """
    # Initialize logger on first call
    logger.ensure_logger("llm_client")

    provider = _detect_provider(model)

    # Log the request
    logger.log_llm_request(model, provider, messages, temperature, max_tokens)

    start_time = time.time()

    try:
        if provider == "openai":
            result = _call_openai(model, messages, temperature, max_tokens, reasoning_effort)
        else:  # anthropic
            result = _call_anthropic(model, messages, temperature, max_tokens, system_message)

        duration_ms = (time.time() - start_time) * 1000
        logger.log_llm_response(result, duration_ms)

        return result
    except Exception as e:
        error_msg = f"{provider.capitalize()} API Error: {e}"
        logger.log_llm_error(error_msg)
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg) from e
