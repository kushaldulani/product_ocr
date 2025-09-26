from pydantic import BaseModel, Field
from typing import List, Optional


class Product(BaseModel):
    name: str = Field(description="Product name with size, material, type (convert inch symbols to 'inch')")
    sku: str = Field(description="Product SKU/Code exactly as shown")
    primary_color: str = Field(description="Base color only (White, Grey, Beige, Black, etc.)")
    secondary_color: str = Field(description="Full finish/color description (White Matte, Grey Matte, Beige Tekno, etc.)")
    color_code: str = Field(description="Hex color code for the primary color (e.g., #FFFFFF for white, #808080 for grey)")
    price: str = Field(description="Product price with currency symbol")


class ProductCatalog(BaseModel):
    products: List[Product]


class ProductResponse(BaseModel):
    name: str
    sku: str
    primary_color: str
    secondary_color: str
    color_code: str
    price: str


class ProcessingResult(BaseModel):
    status: str
    sku: str
    error: Optional[str] = None


class OCRResponse(BaseModel):
    success: bool
    message: str
    extracted_count: int
    saved_count: int
    products: List[ProductResponse]
    results: List[ProcessingResult]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str