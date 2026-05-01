"""AI helpers — Anthropic Claude (text) + Google Gemini (images) + HuggingFace (free).

Reads prompts from the ``prompt_templates`` collection (seeded on startup).
Includes fuzzy duplicate-name detection with retry.

Environment variables:
    ANTHROPIC_API_KEY    - required for product-draft generation
    GEMINI_API_KEY       - required for image enhance / alternates (Gemini)
    HUGGINGFACE_API_KEY  - optional free-tier HuggingFace Inference API key
                           (works without key on public models, with rate limits)
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from typing import Any, Optional

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
GEMINI_IMAGE_MODEL = "gemini-2.0-flash-exp"

# HuggingFace free-tier models
HF_TXT2IMG_MODEL = "black-forest-labs/FLUX.1-schnell"       # best free text-to-image
HF_IMG2IMG_MODEL = "timbrooks/instruct-pix2pix"              # free image-to-image
HF_TEXT_MODEL_DEFAULT = "meta-llama/Llama-3.2-3B-Instruct"  # reliable free-tier chat model

# Ordered fallbacks for HuggingFace text (all support chat_completion on serverless)
HF_TEXT_FALLBACKS = [
    "meta-llama/Llama-3.2-3B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "HuggingFaceH4/zephyr-7b-beta",
]

# Groq — current recommended models (updated when old ones are decommissioned)
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
GROQ_FALLBACKS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]

# Prompt template keys
PT_PRODUCT_DRAFT = "product_draft"
PT_IMAGE_ENHANCE = "image_enhance"
PT_IMAGE_ALTERNATE = "image_alternate"
PT_IMAGE_GENERATE = "image_generate"


# ---------------------------------------------------------------------------
# API key helpers — all async so Motor (async MongoDB) is awaited correctly.
# ---------------------------------------------------------------------------

async def _anthropic_key(db=None) -> str | None:
    """Get Anthropic API key from admin settings or environment."""
    if db:
        try:
            settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
            if settings and settings.get("ai", {}).get("anthropic_api_key"):
                return settings["ai"]["anthropic_api_key"]
        except Exception:
            pass
    return os.environ.get("ANTHROPIC_API_KEY")


async def _gemini_key(db=None) -> str | None:
    """Get Gemini API key from admin settings or environment."""
    if db:
        try:
            settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
            if settings and settings.get("ai", {}).get("gemini_api_key"):
                return settings["ai"]["gemini_api_key"]
        except Exception:
            pass
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return key


async def _openrouter_key(db=None) -> str | None:
    """Get OpenRouter API key from admin settings or environment."""
    if db:
        try:
            settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
            if settings and settings.get("ai", {}).get("openrouter_api_key"):
                return settings["ai"]["openrouter_api_key"]
        except Exception:
            pass
    return os.environ.get("OPENROUTER_API_KEY")


async def _groq_key(db=None) -> str | None:
    """Get Groq API key from admin settings or environment."""
    if db:
        try:
            settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
            if settings and settings.get("ai", {}).get("groq_api_key"):
                return settings["ai"]["groq_api_key"]
        except Exception:
            pass
    return os.environ.get("GROQ_API_KEY")


async def _hf_key(db=None) -> str | None:
    """HuggingFace token — optional, improves rate limits but not required."""
    if db:
        try:
            settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
            if settings and settings.get("ai", {}).get("huggingface_api_key"):
                return settings["ai"]["huggingface_api_key"]
        except Exception:
            pass
    return os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

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
# Text generation
# ---------------------------------------------------------------------------

async def _claude_complete(db, system: str, prompt: str, model: str) -> str:
    """Call Anthropic Messages API and return the assistant text."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError as e:
        raise RuntimeError("anthropic package not installed") from e

    key = await _anthropic_key(db)
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Configure it in Admin Settings → AI Settings "
            "or set as environment variable."
        )
    client = AsyncAnthropic(api_key=key)
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


async def _openrouter_text_generation(db, prompt: str, model: str) -> str:
    """OpenRouter text generation using OpenAI-compatible API."""
    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise RuntimeError("openai package not installed") from e

    key = await _openrouter_key(db)
    if not key:
        raise RuntimeError(
            "OpenRouter API key is required. Add it in Admin Settings → AI Settings "
            "or set OPENROUTER_API_KEY environment variable."
        )
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        return completion.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"OpenRouter API error: {e}") from e


async def _groq_text_generation(db, prompt: str, model: str) -> str:
    """Groq text generation with automatic fallback for decommissioned models."""
    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise RuntimeError("openai package not installed") from e

    key = await _groq_key(db)
    if not key:
        raise RuntimeError(
            "Groq API key is required. Add it in Admin Settings → AI Settings "
            "or set GROQ_API_KEY environment variable."
        )

    client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)

    # Try the requested model first, then fall back through the list
    models_to_try = [model] + [m for m in GROQ_FALLBACKS if m != model]
    last_exc: Exception | None = None

    for m in models_to_try:
        try:
            completion = await client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            logger.info("Groq model '%s' succeeded.", m)
            return completion.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if "decommissioned" in err_str or "model_not_found" in err_str or "404" in err_str:
                logger.warning("Groq model '%s' unavailable, trying next fallback. Error: %s", m, e)
                last_exc = e
                continue
            # Non-model error (auth, rate limit, etc.) — raise immediately
            raise RuntimeError(f"Groq API error: {e}") from e

    raise RuntimeError(
        f"All Groq models are unavailable or decommissioned. "
        f"Last error: {last_exc}. "
        f"Check https://console.groq.com/docs/deprecations for current models."
    )


def _hf_chat_sync(token: str | None, prompt: str, models_to_try: list[str]) -> str:
    """
    Synchronous HuggingFace chat_completion call.

    Uses the serverless /v1/chat/completions endpoint which is the actively
    maintained free-tier path. Run via asyncio.to_thread() from async callers.
    """
    try:
        from huggingface_hub import InferenceClient
    except ImportError as e:
        raise RuntimeError("huggingface_hub package not installed") from e

    client = InferenceClient(token=token)
    last_exc: Exception | None = None

    for model in models_to_try:
        try:
            response = client.chat_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            logger.info("HuggingFace model '%s' succeeded.", model)
            return response.choices[0].message.content
        except Exception as e:
            logger.warning("HuggingFace model '%s' failed: %s", model, e)
            last_exc = e

    err_str = str(last_exc or "")
    if "401" in err_str or "Invalid username" in err_str:
        raise RuntimeError(
            "HuggingFace authentication failed. Check your API key in Admin Settings. "
            f"Error: {last_exc}"
        )
    raise RuntimeError(
        f"All HuggingFace fallback models failed. Last error: {last_exc}"
    )


async def _hf_text_generation(db, prompt: str, model: str) -> str:
    """Async HuggingFace text generation with automatic model fallback."""
    token = await _hf_key(db)
    models_to_try = [model] + [m for m in HF_TEXT_FALLBACKS if m != model]
    return await asyncio.to_thread(_hf_chat_sync, token, prompt, models_to_try)


# ---------------------------------------------------------------------------
# Product draft generation
# ---------------------------------------------------------------------------

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
    last_exc: Exception | None = None

    # Resolve provider and settings once before the retry loop
    settings = await db.admin_settings.find_one({"id": "global"}, {"_id": 0})
    text_provider = (settings or {}).get("ai", {}).get("text_provider", "groq") if settings else "groq"

    for attempt in range(max_retries + 1):
        avoid_section = ""
        if avoid:
            avoid_section = (
                f"\nIMPORTANT: avoid these names entirely "
                f"(too similar to existing): {avoid}"
            )

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
            if text_provider == "anthropic":
                text = await _claude_complete(
                    db, tpl["system_prompt"], prompt, tpl.get("model_name", CLAUDE_MODEL)
                )

            elif text_provider == "openrouter":
                or_prompt = (
                    f"{tpl['system_prompt']}\n\n{prompt}\n\n"
                    "Respond with a single JSON object containing: productName, shortTitle, "
                    "shortDescription, fullDescription, sizes, tags, finalPrice (number only)."
                )
                or_model = (
                    (settings or {}).get("ai", {}).get("openrouter_model")
                    or "meta-llama/llama-3-8b-instruct:free"
                )
                text = await _openrouter_text_generation(db, or_prompt, or_model)

            elif text_provider == "groq":
                groq_prompt = (
                    f"{tpl['system_prompt']}\n\n{prompt}\n\n"
                    "Respond with a single JSON object containing: productName, shortTitle, "
                    "shortDescription, fullDescription, sizes, tags, finalPrice (number only)."
                )
                groq_model = (
                    (settings or {}).get("ai", {}).get("groq_model")
                    or GROQ_MODEL_DEFAULT
                )
                text = await _groq_text_generation(db, groq_prompt, groq_model)

            else:
                # HuggingFace free tier
                hf_prompt = (
                    f"{tpl['system_prompt']}\n\n{prompt}\n\n"
                    "Respond with a single JSON object containing: productName, shortTitle, "
                    "shortDescription, fullDescription, sizes, tags, finalPrice (number only)."
                )
                hf_model = (
                    (settings or {}).get("ai", {}).get("huggingface_text_model")
                    or HF_TEXT_MODEL_DEFAULT
                )
                text = await _hf_text_generation(db, hf_prompt, hf_model)

            draft = _extract_json(text)

        except Exception as e:
            last_exc = e
            logger.exception("AI draft attempt %d failed: %s", attempt, e)
            continue

        dup = is_duplicate(draft.get("productName", ""), existing_names)
        if dup and attempt < max_retries:
            avoid = (avoid + "; " if avoid else "") + dup
            logger.info(
                "Duplicate name '%s' similar to '%s' — retrying.",
                draft.get("productName"),
                dup,
            )
            continue
        break

    if not draft:
        raise last_exc or RuntimeError("AI generation failed after all retries")

    try:
        price = int(draft.get("finalPrice", min_price))
    except Exception:
        price = min_price
    price = max(min_price, min(max_price, price))
    draft["finalPrice"] = price
    draft["_duplicateChecked"] = True
    return draft


# ---------------------------------------------------------------------------
# Image generation — Google Gemini
#
# _gemini_image_call runs in a sync thread via asyncio.to_thread(), so we
# resolve the API key async BEFORE entering the thread and pass it in directly.
# ---------------------------------------------------------------------------

def _gemini_image_call(
    key: str, system: str, prompt: str, image_bytes: bytes, model: str
) -> Optional[bytes]:
    """Synchronous Gemini call; run in a thread from async code."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise RuntimeError("google-genai package not installed") from e

    client = genai.Client(api_key=key)
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
    key = await _gemini_key(db)
    try:
        return await asyncio.to_thread(
            _gemini_image_call,
            key,
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
    key = await _gemini_key(db)
    prompt = fmt(tpl["user_prompt_template"], view=view)
    try:
        return await asyncio.to_thread(
            _gemini_image_call,
            key,
            tpl["system_prompt"],
            prompt,
            image_bytes,
            tpl.get("model_name", GEMINI_IMAGE_MODEL),
        )
    except Exception as e:
        logger.exception("generate_alternate_view failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Image generation — HuggingFace (free / open-source)
# Same pattern: resolve token async before entering the sync thread.
# ---------------------------------------------------------------------------

def _hf_text_to_image(token: str | None, prompt: str, model: str) -> bytes:
    """Synchronous HuggingFace text-to-image; run in a thread."""
    try:
        from huggingface_hub import InferenceClient
        from io import BytesIO
    except ImportError as e:
        raise RuntimeError("huggingface_hub package not installed") from e
    client = InferenceClient(model=model, token=token)
    img = client.text_to_image(prompt)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _hf_image_to_image(
    token: str | None, image_bytes: bytes, prompt: str, model: str
) -> bytes:
    """Synchronous HuggingFace image-to-image; run in a thread."""
    try:
        from huggingface_hub import InferenceClient
        from PIL import Image
        from io import BytesIO
    except ImportError as e:
        raise RuntimeError("huggingface_hub or Pillow not installed") from e
    client = InferenceClient(model=model, token=token)
    source = Image.open(BytesIO(image_bytes)).convert("RGB")
    result = client.image_to_image(image=source, prompt=prompt)
    buf = BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


async def generate_image_from_prompt(db, prompt: str) -> Optional[bytes]:
    """Generate a new product image from text using HuggingFace FLUX (free)."""
    model = os.environ.get("HF_TXT2IMG_MODEL", HF_TXT2IMG_MODEL)
    token = await _hf_key(db)
    try:
        return await asyncio.to_thread(_hf_text_to_image, token, prompt, model)
    except Exception as e:
        logger.exception("generate_image_from_prompt failed: %s", e)
        return None


async def regenerate_image_variation(
    db, image_bytes: bytes, instruction: str
) -> Optional[bytes]:
    """Regenerate an image variation using HuggingFace instruct-pix2pix (free)."""
    model = os.environ.get("HF_IMG2IMG_MODEL", HF_IMG2IMG_MODEL)
    prompt = (
        instruction
        or "luxury fashion product photo, clean studio background, editorial lighting"
    )
    token = await _hf_key(db)
    try:
        return await asyncio.to_thread(_hf_image_to_image, token, image_bytes, prompt, model)
    except Exception as e:
        logger.exception("regenerate_image_variation failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Default seed prompts — only inserted if collection is empty.
# ---------------------------------------------------------------------------
DEFAULT_PROMPTS: list[dict] = [
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
            "Target price band: {{min_price}}-{{max_price}} {{currency}} "
            "(category multiplier {{category_multiplier}})\n"
            "{{image_hint}}\n"
            "Avoid reusing these existing names: {{avoid_names}}\n\n"
            "Requirements:\n"
            "- productName: 3-6 words, elegant, catalog-ready, blends 1-2 naming families naturally.\n"
            "- shortTitle: 4-8 words, premium commerce title.\n"
            "- shortDescription: 1-2 sentences, refined tone.\n"
            "- fullDescription: 3-5 sentences, evokes craftsmanship, occasion, silhouette, fabric. No pricing talk.\n"
            "- tags: 4-8 lowercase keywords.\n"
            "- sizes: subset of the size template appropriate for the piece.\n"
            "- finalPrice: integer in {{currency}}, WITHIN {{min_price}}-{{max_price}}, quietly informed by "
            "perceived quality, complexity, embellishment, occasion, and category multiplier. "
            "Do NOT mention any research.\n"
            "- pricingMeta (internal, admin-only): object with perceivedQuality (1-5), complexity (1-5), "
            "occasionTier (\"daily\"|\"occasion\"|\"statement\"|\"ceremony\"), uplift (0.0-1.0), "
            "reasoning (one short sentence).\n\n"
            "Return exactly this JSON shape:\n"
            "{\n"
            "  \"productName\": \"...\",\n"
            "  \"shortTitle\": \"...\",\n"
            "  \"shortDescription\": \"...\",\n"
            "  \"fullDescription\": \"...\",\n"
            "  \"tags\": [\"...\", \"...\"],\n"
            "  \"sizes\": [\"S\",\"M\",\"L\"],\n"
            "  \"finalPrice\": 89,\n"
            "  \"pricingMeta\": { \"perceivedQuality\": 4, \"complexity\": 3, "
            "\"occasionTier\": \"occasion\", \"uplift\": 0.15, \"reasoning\": \"...\" }\n"
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