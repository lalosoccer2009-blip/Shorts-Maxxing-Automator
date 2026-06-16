"""
Calls Google's Gemini API (free tier) to draft a title, description, and
tags for a Short, based on the channel's niche/tone/audience.

Requires the GEMINI_API_KEY environment variable to be set. See README.md
Step 4 for how to get a free key.
"""

import json
import os
import re

import requests

# Google periodically renames/replaces which model is on the free tier.
# If you get a "model not found" style error, check
# https://ai.google.dev/gemini-api/docs/models for the current free Flash
# model name and update this constant.
GEMINI_MODEL = "gemini-2.5-flash"

API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

PROMPT_TEMPLATE = """You are writing YouTube Shorts metadata for a channel.

Channel niche: {niche}
Tone: {tone}
Audience: {audience}
Video file name (may hint at the content): {filename}
Extra notes from the creator: {extra_notes}

Write metadata for this Short. Respond with ONLY valid JSON, no markdown
formatting, no code fences, no commentary before or after it. Use exactly
this shape:

{{"title": "...", "description": "...", "tags": ["tag1", "tag2"]}}

Rules:
- title: under 100 characters, attention-grabbing but not misleading
- description: 2-4 sentences, can end with a couple of relevant hashtags
- tags: 6-10 relevant lowercase keywords, no '#' symbol
"""


def _extract_json(text):
    """Pull a JSON object out of the model's reply even if it added
    stray formatting around it."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def generate_metadata(channel_cfg, filename, extra_notes=""):
    """Returns a dict: {"title": ..., "description": ..., "tags": [...]}"""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. See README.md "
            "Step 4."
        )

    prompt = PROMPT_TEMPLATE.format(
        niche=channel_cfg.get("niche", ""),
        tone=channel_cfg.get("tone", ""),
        audience=channel_cfg.get("audience", ""),
        filename=filename,
        extra_notes=extra_notes or "(none)",
    )

    response = requests.post(
        API_URL,
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response from Gemini: {data}") from e

    try:
        metadata = _extract_json(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Could not parse Gemini's reply as JSON. Raw reply:\n{raw_text}"
        ) from e

    metadata.setdefault("title", "Untitled Short")
    metadata.setdefault("description", "")
    metadata.setdefault("tags", [])

    if len(metadata["title"]) > 100:
        metadata["title"] = metadata["title"][:97] + "..."

    return metadata
