"""AI helpers — Claude Sonnet 4.5 (text) + Gemini Nano Banana (images).

Prompts are read from MongoDB collection `prompt_templates` (seeded on startup).
Includes fuzzy duplicate-name detection with retry.

NOTE: Emergent LLM integration disabled - emergentintegrations package not available.
AI functionality using Emergent services will return errors.
"""
import os
import json
import base64
import logging
import random
import re
import uuid
from typing import Optional, Any

# from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
# Emergent integration disabled - package not available on public PyPI
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
NANO_BANANA_MODEL = "gemini-3.1-flash-image-preview"

# Prompt template keys
PT_PRODUCT_DRAFT = "product_draft"
PT_IMAGE_ENHANCE = "image_enhance"
PT_IMAGE_ALTERNATE = "image_alternate"


def _api_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    return key


def _emergent_available() -> bool:
    """Check if Emergent LLM integration is available."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        return True
    except ImportError:
        logger.warning("Emergent LLM integration not available - AI features disabled")
        return False


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    raise ValueError("No JSON in response")


def fmt(template: str, **kwargs: Any) -> str:
    """Safe template substitution — replaces {{key}} placeholders."""
    out = template
    for k, v in kwargs.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def is_duplicate(name: str, existing: list[str], threshold: int = 85) -> Optional[str]:
    """Return the matching existing name if `name` is too similar, else None."""
    if not name:
        return None
    name_n = name.strip().lower()
    for e in existing:
        if not e: continue
        ratio = fuzz.token_set_ratio(name_n, e.strip().lower())
        if ratio >= threshold:
            return e
    return None


async def _get_template(db, key: str) -> dict:
    tpl = await db.prompt_templates.find_one({"key": key, "enabled": True}, {"_id": 0})
    if not tpl:
        raise RuntimeError(f"Prompt template '{key}' not found")
    return tpl


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
    if image_description: image_hint_parts.append(f"Source image description: {image_description}")
    if image_tags: image_hint_parts.append(f"Image tags: {', '.join(image_tags)}")
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

        chat = LlmChat(
            api_key=_api_key(),
            session_id=f"product-gen-{uuid.uuid4()}",
            system_message=tpl["system_prompt"],
        ).with_model(tpl.get("model_provider", "anthropic"), tpl.get("model_name", CLAUDE_MODEL))

        try:
            resp = await chat.send_message(UserMessage(text=prompt))
            draft = _extract_json(resp)
        except Exception as e:
            logger.exception("AI draft attempt %d failed: %s", attempt, e)
            continue

        # Duplicate check
        dup = is_duplicate(draft.get("productName", ""), existing_names)
        if dup and attempt < max_retries:
            avoid = (avoid + "; " if avoid else "") + dup
            logger.info("duplicate name '%s' similar to '%s' — retrying", draft.get("productName"), dup)
            continue
        break

    if not draft:
        raise RuntimeError("AI generation failed")

    # Clamp price defensively.
    try:
        price = int(draft.get("finalPrice", min_price))
    except Exception:
        price = min_price
    price = max(min_price, min(max_price, price))
    draft["finalPrice"] = price
    draft["_duplicateChecked"] = True
    return draft


async def enhance_image(db, image_bytes: bytes) -> Optional[bytes]:
    tpl = await _get_template(db, PT_IMAGE_ENHANCE)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    chat = LlmChat(
        api_key=_api_key(),
        session_id=f"img-enhance-{uuid.uuid4()}",
        system_message=tpl["system_prompt"],
    ).with_model(tpl.get("model_provider", "gemini"), tpl.get("model_name", NANO_BANANA_MODEL)).with_params(modalities=["image", "text"])

    msg = UserMessage(text=tpl["user_prompt_template"], file_contents=[ImageContent(b64)])
    try:
        _text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        logger.exception("enhance_image failed: %s", e)
        return None
    if not images:
        return None
    return base64.b64decode(images[0]["data"])


async def generate_alternate_view(db, image_bytes: bytes, view: str) -> Optional[bytes]:
    tpl = await _get_template(db, PT_IMAGE_ALTERNATE)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    chat = LlmChat(
        api_key=_api_key(),
        session_id=f"img-alt-{uuid.uuid4()}",
        system_message=tpl["system_prompt"],
    ).with_model(tpl.get("model_provider", "gemini"), tpl.get("model_name", NANO_BANANA_MODEL)).with_params(modalities=["image", "text"])

    prompt = fmt(tpl["user_prompt_template"], view=view)
    msg = UserMessage(text=prompt, file_contents=[ImageContent(b64)])
    try:
        _text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        logger.exception("generate_alternate_view failed: %s", e)
        return None
    if not images:
        return None
    return base64.b64decode(images[0]["data"])


# Default seed prompts — only inserted if collection empty.
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
        "model_name": NANO_BANANA_MODEL,
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
        "model_name": NANO_BANANA_MODEL,
        "system_prompt": "You are an expert product photo editor for a luxury fashion catalog.",
        "user_prompt_template": (
            "Create an alternate catalog photograph of the same garment shown here. "
            "View: {{view}}. Preserve fabric, colors, pattern and silhouette exactly. "
            "Editorial lighting, subtle neutral background, premium African luxury styling."
        ),
        "enabled": True,
    },
]
