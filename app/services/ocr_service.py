import base64
import requests
import random
import string
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from app.core.config import settings
from app.models.schemas import Product, ProductCatalog


# Extraction prompt
EXTRACTION_PROMPT = """
# Product Catalog Extraction System Prompt

You are a specialized product information extraction assistant. Your task is to analyze product catalog images and extract structured information about ONLY the specifically highlighted or indicated product variants.

## Critical Extraction Rules:

1. **ONLY Extract Specifically Indicated Items**: 
   - Extract ONLY the exact variants that have visual indicators pointing to them
   - Visual indicators include: circles, arrows, highlighting, boxes, or any marking that emphasizes specific items
   - DO NOT extract all available variants just because one variant is highlighted
   - Each visual indicator represents ONE specific product entry to extract

2. **Visual Indicator Interpretation**:
   - Circles/highlights around specific codes or text = Extract ONLY those specific items
   - Arrows pointing to specific rows/entries = Extract ONLY those pointed-to items
   - If an indicator points between items, determine which specific item(s) it indicates
   - The number of visual indicators determines the number of products to extract

3. **Variant/Option Selection Rules**:
   - When a product has multiple options (colors, finishes, sizes, etc.):
     - ONLY extract the option(s) with visual indicators
     - Do NOT extract all available options unless each has its own indicator
   - Match each variant to its corresponding price in the catalog
   - If unclear which specific variant is indicated, use the one closest to the indicator

4. **Extract Product Information**: For each SPECIFICALLY highlighted variant, extract:
   - Product name/description
   - Product code/SKU as shown
   - Variant/finish/color information
   - Corresponding price for that specific variant
   - Any other relevant specifications shown

5. **Color/Finish Extraction Rules**:
   - **Primary Color/Category**: Extract the base descriptor (main color, material, or category)
   - **Secondary Color/Specification**: Extract the full detailed description including finish, texture, or complete variant name
   - If the catalog uses codes, decode them based on visible legends or patterns
   - If only one descriptor exists, use it for both primary and secondary fields

6. **Price Matching**:
   - Each variant typically has its own price in a corresponding column or row
   - Match the highlighted variant to its specific price
   - Do NOT apply one price to all variants unless that's how the catalog shows it

7. **Data Cleaning Rules**:
   - Convert special symbols for JSON compatibility (e.g., " to inch, ® to (R))
   - Preserve original SKU/code formatting
   - Include currency symbols with prices
   - Maintain catalog's naming conventions

## Validation Process:
Before outputting, verify:
- Number of extracted products equals number of visual indicators
- Each extracted entry corresponds to a specific visual indicator
- No duplicate entries unless separately indicated
- Prices correctly match their specific variants

## Output Rules:
- Return ONLY items with direct visual indicators
- Count visual indicators and extract exactly that many products
- Each visual indicator = one product entry
- Do not infer or add items not specifically pointed to

## Interpretation Guidelines:
- Analyze the catalog's structure to understand how variants are organized
- Look for patterns in how colors/finishes/options are labeled
- Use context clues to decode abbreviations or codes
- Match the catalog's terminology without assuming standard naming
- Don't extract anything if it is not highlighted or indicated

## Field Guidelines:
- **name**: Full descriptive name as shown in catalog
- **sku/code**: Exact product code from catalog
- **primary_attribute**: Base characteristic (color, material, type, etc.)
- **secondary_attribute**: Full detailed specification
- **price**: Price specific to that variant

## Universal Application:
This prompt works for:
- Any product type (furniture, electronics, clothing, etc.)
- Any naming convention (codes, full names, abbreviations)
- Any language or terminology
- Any catalog layout or structure

Remember: Let the visual indicators guide your extraction. Extract exactly what is indicated, nothing more, nothing less.

"""


def extract_products(image_path: str) -> ProductCatalog:
    """Extract products from catalog image using Gemini"""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0
    ).with_structured_output(ProductCatalog)

    message = HumanMessage(
        content=[
            {"type": "text", "text": EXTRACTION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
        ]
    )

    return llm.invoke([message])


def parse_price(price_str: str) -> float:
    """Convert price string to float (e.g., '$595' -> 595.0)"""
    price_clean = price_str.replace('$', '').replace(',', '').strip()
    try:
        return float(price_clean)
    except:
        return 0.0


def lookup_product_by_sku(sku: str) -> dict:
    """Lookup existing product by SKU"""
    try:
        response = requests.get(
            f"http://35.182.153.121:5001/api/products/sku/{sku}",
            headers={'accept': 'application/json'},
            timeout=settings.database_timeout
        )
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('data'):
                return result['data']
    except:
        pass
    return None


def generate_variant_sku(base_sku: str, secondary_color: str) -> str:
    """Generate a variant SKU by adding space and secondary color"""
    # Clean the secondary color to make it SKU-friendly
    clean_color = secondary_color.strip().replace(' ', '_')
    return f"{base_sku} {clean_color}"


def normalize_color(color: str) -> str:
    """Normalize color string for comparison"""
    if not color:
        return ""
    return color.strip().lower().replace(' ', '').replace('-', '').replace('_', '')


def save_product_to_db(product: Product) -> dict:
    """Save a single product to the database via API with duplicate/variant handling"""
    price_value = parse_price(product.price)
    original_sku = product.sku
    final_sku = original_sku

    # Normalize colors for comparison
    new_primary_color_norm = normalize_color(product.primary_color)

    # First, check if base SKU exists
    base_product = lookup_product_by_sku(original_sku)

    if base_product:
        base_color_norm = normalize_color(base_product.get('color', ''))

        if base_color_norm == new_primary_color_norm:
            # Same SKU, same color - it's a duplicate
            return {
                "status": "duplicate",
                "sku": original_sku,
                "error": f"Product already exists in database with SKU {original_sku} and color {product.primary_color}"
            }

    # If base SKU exists with different color OR doesn't exist, check variant SKU
    # Use secondary_color if available, otherwise use primary_color
    color_suffix = product.secondary_color if hasattr(product, 'secondary_color') and product.secondary_color else product.primary_color
    variant_sku = generate_variant_sku(original_sku, color_suffix)

    # Check if this variant SKU already exists
    variant_product = lookup_product_by_sku(variant_sku)

    if variant_product:
        variant_color_norm = normalize_color(variant_product.get('color', ''))
        if variant_color_norm == new_primary_color_norm:
            # Variant with same color already exists
            return {
                "status": "duplicate",
                "sku": variant_sku,
                "error": f"Product variant already exists with SKU {variant_sku} and color {product.primary_color}"
            }

    # Determine final SKU to use
    if base_product:
        # Base SKU exists with different color, use variant SKU
        final_sku = variant_sku
        variant_message = f"Created variant SKU {final_sku} for {original_sku} with {color_suffix}"
    else:
        # Base SKU doesn't exist, use original SKU
        final_sku = original_sku
        variant_message = None

    payload = {
        "name": product.name.replace('\n', ' '),
        "sku": final_sku,
        "color": product.primary_color,
        "pricing": {
            "price": price_value,
            "regular_price": price_value
        }
    }

    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(
            settings.database_api_url,
            headers=headers,
            json=payload,
            timeout=settings.database_timeout
        )
        response.raise_for_status()

        result = {
            "status": "success",
            "sku": final_sku,
            "response": response.json()
        }

        # Add variant info if applicable
        if variant_message:
            result["variant_info"] = variant_message
            result["original_sku"] = original_sku

        return result

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "sku": final_sku,
            "original_sku": original_sku if final_sku != original_sku else None,
            "error": str(e),
            "response": response.text if 'response' in locals() else None
        }