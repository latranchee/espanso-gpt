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

# Lazy-loaded clients to avoid import errors if one SDK is missing
_openai_client = None
_anthropic_client = None


def _get_openai_client():
    """Lazily initialize and return the OpenAI client."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _get_anthropic_client():
    """Lazily initialize and return the Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        _anthropic_client = Anthropic(api_key=api_key)
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
    max_tokens: int
) -> str:
    """Make an OpenAI API call."""
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content.strip()


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

    # Convert messages to Anthropic format
    anthropic_messages = _convert_messages_for_anthropic(messages)

    # Build API call arguments
    api_args: dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    if system_message:
        api_args["system"] = system_message

    response = client.messages.create(**api_args)
    return response.content[0].text.strip()


def create_chat_completion(
    model: str,
    messages: list[dict],
    temperature: float = 0.6,
    max_tokens: int = 2000,
    system_message: str | None = None
) -> str:
    """
    Create a chat completion using the appropriate provider.

    Provider is auto-detected from model name:
    - claude-* -> Anthropic
    - gpt-*, o1-* -> OpenAI

    Args:
        model: The model identifier (e.g., "claude-haiku-4-5-20251001", "gpt-4o-mini")
        messages: List of message dicts with "role" and "content" keys.
                  For images, use OpenAI format - will be converted for Anthropic.
        temperature: Sampling temperature (0.0 to 1.0)
        max_tokens: Maximum tokens in response
        system_message: Optional system message (for Anthropic, passed separately)

    Returns:
        The assistant's response text.

    Raises:
        ValueError: If provider cannot be detected or API key is missing.
    """
    # Initialize logger on first call
    logger.init_logger("llm_client")

    provider = _detect_provider(model)

    # Log the request
    logger.log_llm_request(model, provider, messages, temperature, max_tokens)

    start_time = time.time()

    try:
        if provider == "openai":
            result = _call_openai(model, messages, temperature, max_tokens)
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
