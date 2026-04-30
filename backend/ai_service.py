"""AI helpers — Anthropic Claude (text) + Google Gemini (images).

Reads prompts from the ``prompt_templates`` collection (seeded on startup).
Includes fuzzy duplicate-name detection with retry. Uses official Anthropic
and Google ``google-genai`` SDKs directly. The previous Emergent integration
has been removed.

Environment variables:
    ANTHROPIC_API_KEY  - required for product-draft generation
    GEMINI_API_KEY     - required for image enhance / alternates
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import uuid
from typing import Any, Optional

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image-preview"

# Prompt template keys
PT_PRODUCT_DRAFT = "product_draft"
PT_IMAGE_ENHANCE = "image_enhance"
PT_IMAGE_ALTERNATE = "image_alternate"


def _anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


def _gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return key


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    raise ValueError("No JSON in response")


def fmt(template: str, **kwargs: Any) -> str:
    """Safe template substitution — replaces ``{{key}}`` placeholders."""
    out = template
    for k, v in kwargs.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def is_duplicate(name: str, existing: list[str], threshold: int = 85) -> Optional[str]:
    if not name:
        return None
    name_n = name.strip().lower()
    for e in existing:
        if not e:
            continue
        ratio = fuzz.token_set_ratio(name_n, e.strip().lower())
        if ratio >= threshold:
            return e
    return None


async def _get_template(db, key: str) -> dict:
    tpl = await db.prompt_templates.find_one({"key": key, "enabled": True}, {"_id": 0})
    if not tpl:
        raise RuntimeError(f"Prompt template '{key}' not found")
    return tpl


# ---------------------------------------------------------------------------
# Text generation (Anthropic)
# ---------------------------------------------------------------------------

async def _claude_complete(system: str, prompt: str, model: str) -> str:
    """Call Anthropic Messages API and return the assistant text."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("anthropic package not installed") from e

    client = AsyncAnthropic(api_key=_anthropic_key())
    msg = await client.messages.create(
        model=model or CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


async def generate_product_draft(
    *,
    db,
    category: str,
    naming_families: list[dict],
    pricing_rules: dict,
    size_template: list[str],
    image_tags: Optional[list[str]] = None,
    image_description: Optional[str] = None,
    existing_names: Optional[list[str]] = None,
    max_retries: int = 2,
) -> dict:
    tpl = await _get_template(db, PT_PRODUCT_DRAFT)
    enabled_families = [f for f in naming_families if f.get("enabled", True)]
    families_text = "\n".join(
        f"- {f['name']}: {', '.join(f.get('words', [])[:12])}"
        for f in enabled_families
    )

    min_price = pricing_rules.get("min_price", 40)
    max_price = pricing_rules.get("max_price", 150)
    currency = pricing_rules.get("currency", "USD")
    category_mult = (pricing_rules.get("category_multipliers") or {}).get(category, 1.0)

    image_hint_parts = []
    if image_description:
        image_hint_parts.append(f"Source image description: {image_description}")
    if image_tags:
        image_hint_parts.append(f"Image tags: {', '.join(image_tags)}")
    image_hint = "\n".join(image_hint_parts)

    existing_names = existing_names or []
    avoid = ""
    draft: dict = {}

    for attempt in range(max_retries + 1):
        avoid_section = ""
        if avoid:
            avoid_section = f"\nIMPORTANT: avoid these names entirely (too similar already exists): {avoid}"

        prompt = fmt(
            tpl["user_prompt_template"],
            category=category,
            families_text=families_text or "(no families configured)",
            size_template=size_template,
            min_price=min_price,
            max_price=max_price,
            currency=currency,
            category_multiplier=f"{category_mult:.2f}",
            image_hint=image_hint,
            avoid_names="; ".join(existing_names[:30]) + avoid_section,
        )

        try:
            text = await _claude_complete(
                tpl["system_prompt"], prompt, tpl.get("model_name", CLAUDE_MODEL)
            )
            draft = _extract_json(text)
        except Exception as e:
            logger.exception("AI draft attempt %d failed: %s", attempt, e)
            continue

        dup = is_duplicate(draft.get("productName", ""), existing_names)
        if dup and attempt < max_retries:
            avoid = (avoid + "; " if avoid else "") + dup
            logger.info(
                "duplicate name '%s' similar to '%s' — retrying",
                draft.get("productName"),
                dup,
            )
            continue
        break

    if not draft:
        raise RuntimeError("AI generation failed")

    try:
        price = int(draft.get("finalPrice", min_price))
    except Exception:
        price = min_price
    price = max(min_price, min(max_price, price))
    draft["finalPrice"] = price
    draft["_duplicateChecked"] = True
    return draft


# ---------------------------------------------------------------------------
# Image generation (Google Gemini)
# ---------------------------------------------------------------------------

def _gemini_image_call(system: str, prompt: str, image_bytes: bytes, model: str) -> Optional[bytes]:
    """Synchronous Gemini call; run in a thread from async code."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("google-genai package not installed") from e

    client = genai.Client(api_key=_gemini_key())
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    contents = [system + "\n\n" + prompt, image_part]
    resp = client.models.generate_content(
        model=model or GEMINI_IMAGE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    for cand in getattr(resp, "candidates", []) or []:
        content = getattr(cand, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, str):
                    return base64.b64decode(data)
                return bytes(data)
    return None


async def enhance_image(db, image_bytes: bytes) -> Optional[bytes]:
    tpl = await _get_template(db, PT_IMAGE_ENHANCE)
    try:
        return await asyncio.to_thread(
            _gemini_image_call,
            tpl["system_prompt"],
            tpl["user_prompt_template"],
            image_bytes,
            tpl.get("model_name", GEMINI_IMAGE_MODEL),
        )
    except Exception as e:
        logger.exception("enhance_image failed: %s", e)
        return None


async def generate_alternate_view(db, image_bytes: bytes, view: str) -> Optional[bytes]:
    tpl = await _get_template(db, PT_IMAGE_ALTERNATE)
    prompt = fmt(tpl["user_prompt_template"], view=view)
    try:
        return await asyncio.to_thread(
            _gemini_image_call,
            tpl["system_prompt"],
            prompt,
            image_bytes,
            tpl.get("model_name", GEMINI_IMAGE_MODEL),
        )
    except Exception as e:
        logger.exception("generate_alternate_view failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Default seed prompts — only inserted if collection empty.
# ---------------------------------------------------------------------------
DEFAULT_PROMPTS = [
    {
        "key": PT_PRODUCT_DRAFT,
        "name": "Product draft generator",
        "description": "Generates polished product entries (name, descriptions, sizes, silent pricing).",
        "model_provider": "anthropic",
        "model_name": CLAUDE_MODEL,
        "system_prompt": (
            "You are the in-house product copy engine for Gems & Luxury, an African "
            "luxury fashion brand based in the USA. You create polished, catalog-ready "
            "product entries that read premium, original, and refined. You always "
            "respond with a single JSON object — no commentary, no markdown fences."
        ),
        "user_prompt_template": (
            "Generate ONE premium product entry for a Gems & Luxury item.\n\n"
            "Category: {{category}}\n"
            "Naming families available (blend tastefully, do not stack all):\n"
            "{{families_text}}\n\n"
            "Suggested sizes template: {{size_template}}\n"
            "Target price band: {{min_price}}-{{max_price}} {{currency}} (category multiplier {{category_multiplier}})\n"
            "{{image_hint}}\n"
            "Avoid reusing these existing names: {{avoid_names}}\n\n"
            "Requirements:\n"
            "- productName: 3-6 words, elegant, catalog-ready, blends 1-2 naming families naturally.\n"
            "- shortTitle: 4-8 words, premium commerce title.\n"
            "- shortDescription: 1-2 sentences, refined tone.\n"
            "- fullDescription: 3-5 sentences, evokes craftsmanship, occasion, silhouette, fabric. No pricing talk.\n"
            "- tags: 4-8 lowercase keywords.\n"
            "- sizes: subset of the size template appropriate for the piece.\n"
            "- finalPrice: integer in {{currency}}, WITHIN {{min_price}}-{{max_price}}, quietly informed by perceived quality, "
            "complexity, embellishment, occasion, and category multiplier. Do NOT mention any research.\n"
            "- pricingMeta (internal, admin-only): object with perceivedQuality (1-5), complexity (1-5), "
            "occasionTier (\"daily\"|\"occasion\"|\"statement\"|\"ceremony\"), uplift (0.0-1.0), reasoning (one short sentence).\n\n"
            "Return exactly this JSON shape:\n"
            "{\n"
            "  \"productName\": \"...\",\n"
            "  \"shortTitle\": \"...\",\n"
            "  \"shortDescription\": \"...\",\n"
            "  \"fullDescription\": \"...\",\n"
            "  \"tags\": [\"...\", \"...\"],\n"
            "  \"sizes\": [\"S\",\"M\",\"L\"],\n"
            "  \"finalPrice\": 89,\n"
            "  \"pricingMeta\": { \"perceivedQuality\": 4, \"complexity\": 3, \"occasionTier\": \"occasion\", \"uplift\": 0.15, \"reasoning\": \"...\" }\n"
            "}\n"
        ),
        "enabled": True,
    },
    {
        "key": PT_IMAGE_ENHANCE,
        "name": "Image cleanup & enhance",
        "description": "Cleans background and improves lighting on product photos.",
        "model_provider": "gemini",
        "model_name": GEMINI_IMAGE_MODEL,
        "system_prompt": "You are an expert product photo editor for a luxury fashion catalog.",
        "user_prompt_template": (
            "Take this product photo for a premium African luxury fashion catalog and "
            "clean the background and enhance lighting. Keep the garment identical. "
            "Produce a clean, softly lit, editorial studio result on a subtle neutral background. "
            "Return an image."
        ),
        "enabled": True,
    },
    {
        "key": PT_IMAGE_ALTERNATE,
        "name": "Alternate-view generator",
        "description": "Generates an alternate-angle product photo from a reference.",
        "model_provider": "gemini",
        "model_name": GEMINI_IMAGE_MODEL,
        "system_prompt": "You are an expert product photo editor for a luxury fashion catalog.",
        "user_prompt_template": (
            "Create an alternate catalog photograph of the same garment shown here. "
            "View: {{view}}. Preserve fabric, colors, pattern and silhouette exactly. "
            "Editorial lighting, subtle neutral background, premium African luxury styling."
        ),
        "enabled": True,
    },
]
