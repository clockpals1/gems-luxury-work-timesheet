"""AI helpers — Claude Sonnet 4.5 (text) + Gemini Nano Banana (images)."""
import os
import json
import base64
import logging
import random
import re
import uuid
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
NANO_BANANA_MODEL = "gemini-3.1-flash-image-preview"


def _api_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    return key


def _extract_json(text: str) -> dict:
    """Pull the first valid JSON object out of a Claude response."""
    # Try fenced code block first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Greedy braces
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    raise ValueError("No JSON in response")


async def generate_product_draft(
    *,
    category: str,
    naming_families: list[dict],
    pricing_rules: dict,
    size_template: list[str],
    image_tags: Optional[list[str]] = None,
    image_description: Optional[str] = None,
    existing_names: Optional[list[str]] = None,
) -> dict:
    """Return a product draft dict via Claude Sonnet 4.5.

    Pricing is analysed silently; output exposes only a clean final_price number.
    pricing_meta is returned for admin-only visibility.
    """
    enabled_families = [f for f in naming_families if f.get("enabled", True)]
    families_text = "\n".join(
        f"- {f['name']}: {', '.join(f.get('words', [])[:12])}"
        for f in enabled_families
    ) or "- Royal, Ankara, Heritage, Couture, Grace"

    min_price = pricing_rules.get("min_price", 40)
    max_price = pricing_rules.get("max_price", 150)
    currency = pricing_rules.get("currency", "USD")
    category_mult = (pricing_rules.get("category_multipliers") or {}).get(category, 1.0)

    image_hint = ""
    if image_description:
        image_hint += f"\nSource image description: {image_description}"
    if image_tags:
        image_hint += f"\nImage tags: {', '.join(image_tags)}"

    dedupe = ""
    if existing_names:
        dedupe = "\nAvoid reusing these existing names: " + "; ".join(existing_names[:25])

    system = (
        "You are the in-house product copy engine for Gems & Luxury, an African "
        "luxury fashion brand based in the USA. You create polished, catalog-ready "
        "product entries that read premium, original, and refined. You always "
        "respond with a single JSON object — no commentary, no markdown fences."
    )

    prompt = f"""Generate ONE premium product entry for a Gems & Luxury item.

Category: {category}
Naming families available (blend tastefully, do not stack all):
{families_text}

Suggested sizes template: {size_template}
Target price band: {min_price}-{max_price} {currency} (category multiplier {category_mult:.2f})
{image_hint}
{dedupe}

Requirements:
- productName: 3-6 words, elegant, catalog-ready, blends 1-2 naming families naturally.
- shortTitle: 4-8 words, premium commerce title.
- shortDescription: 1-2 sentences, refined tone.
- fullDescription: 3-5 sentences, evokes craftsmanship, occasion, silhouette, fabric. No pricing talk.
- tags: 4-8 lowercase keywords.
- sizes: subset of the size template appropriate for the piece.
- finalPrice: integer in {currency}, WITHIN {min_price}-{max_price}, quietly informed by perceived quality,
  complexity, embellishment, occasion, and category multiplier. Do NOT mention any research.
- pricingMeta (internal, admin-only): object with perceivedQuality (1-5), complexity (1-5),
  occasionTier ("daily"|"occasion"|"statement"|"ceremony"), uplift (0.0-1.0), reasoning (one short sentence).

Return exactly this JSON shape:
{{
  "productName": "...",
  "shortTitle": "...",
  "shortDescription": "...",
  "fullDescription": "...",
  "tags": ["...", "..."],
  "sizes": ["S","M","L"],
  "finalPrice": 89,
  "pricingMeta": {{ "perceivedQuality": 4, "complexity": 3, "occasionTier": "occasion", "uplift": 0.15, "reasoning": "..." }}
}}
"""
    chat = LlmChat(
        api_key=_api_key(),
        session_id=f"product-gen-{uuid.uuid4()}",
        system_message=system,
    ).with_model("anthropic", CLAUDE_MODEL)

    resp = await chat.send_message(UserMessage(text=prompt))
    try:
        draft = _extract_json(resp)
    except Exception as e:
        logger.exception("Failed to parse product draft JSON: %s", e)
        # fallback
        draft = {
            "productName": "Royal Ankara Grace Gown",
            "shortTitle": "Premium Ankara Occasion Dress",
            "shortDescription": "An elegant African luxury statement piece crafted for refined occasions.",
            "fullDescription": "A premium African fashion piece designed to blend culture, elegance, and modern sophistication.",
            "tags": ["ankara", "luxury", "royal", "african fashion"],
            "sizes": size_template[:4],
            "finalPrice": random.randint(min_price, max_price),
            "pricingMeta": {"perceivedQuality": 4, "complexity": 3, "occasionTier": "occasion", "uplift": 0.15, "reasoning": "fallback"},
        }

    # Clamp price into band defensively.
    try:
        price = int(draft.get("finalPrice", min_price))
    except Exception:
        price = min_price
    price = max(min_price, min(max_price, price))
    draft["finalPrice"] = price
    return draft


async def enhance_image(image_bytes: bytes, instruction: str = "clean background and enhance lighting") -> Optional[bytes]:
    """Return enhanced image bytes via Nano Banana, or None on failure."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    chat = LlmChat(
        api_key=_api_key(),
        session_id=f"img-enhance-{uuid.uuid4()}",
        system_message="You are an expert product photo editor for a luxury fashion catalog.",
    ).with_model("gemini", NANO_BANANA_MODEL).with_params(modalities=["image", "text"])

    prompt = (
        f"Take this product photo for a premium African luxury fashion catalog and "
        f"{instruction}. Keep the garment identical. Produce a clean, softly lit, "
        f"editorial studio result on a subtle neutral background. Return an image."
    )
    msg = UserMessage(text=prompt, file_contents=[ImageContent(b64)])
    try:
        _text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        logger.exception("enhance_image failed: %s", e)
        return None
    if not images:
        return None
    return base64.b64decode(images[0]["data"])


async def generate_alternate_view(image_bytes: bytes, view: str) -> Optional[bytes]:
    """Generate one alternate product-view image."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    chat = LlmChat(
        api_key=_api_key(),
        session_id=f"img-alt-{uuid.uuid4()}",
        system_message="You are an expert product photo editor for a luxury fashion catalog.",
    ).with_model("gemini", NANO_BANANA_MODEL).with_params(modalities=["image", "text"])

    prompt = (
        f"Create an alternate catalog photograph of the same garment shown here. "
        f"View: {view}. Preserve fabric, colors, pattern and silhouette exactly. "
        f"Editorial lighting, subtle neutral background, premium African luxury styling."
    )
    msg = UserMessage(text=prompt, file_contents=[ImageContent(b64)])
    try:
        _text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        logger.exception("generate_alternate_view failed: %s", e)
        return None
    if not images:
        return None
    return base64.b64decode(images[0]["data"])
