import base64
import requests
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


def save_product_to_db(product: Product) -> dict:
    """Save a single product to the database via API"""
    price_value = parse_price(product.price)

    payload = {
        "name": product.name.replace('\n', ' '),
        "sku": product.sku,
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
        return {
            "status": "success",
            "sku": product.sku,
            "response": response.json()
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "sku": product.sku,
            "error": str(e),
            "response": response.text if 'response' in locals() else None
        }