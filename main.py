"""
Product OCR API - Main FastAPI application.

A REST API for extracting product information from catalog images using
Google Gemini Vision and saving the results to a database.

Author: Product OCR Team
Version: 1.0.0
"""

import tempfile
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import OCRResponse, ProductResponse, ProcessingResult
from services import OCRService, DatabaseService, MessageService

# Initialize FastAPI app
app = FastAPI(
    title="Product OCR API",
    description="Extract product information from catalog images using AI vision",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for web frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
ocr_service = OCRService()
database_service = DatabaseService()
message_service = MessageService()


@app.get("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        dict: Simple health status
    """
    return {"status": "healthy", "service": "Product OCR API"}


@app.post("/process-catalog", response_model=OCRResponse)
async def process_catalog_image(file: UploadFile = File(...)):
    """
    Process a catalog image to extract product information.

    This endpoint accepts an image file, extracts product information using
    Google Gemini Vision AI, and attempts to save the products to the database.

    Args:
        file: Uploaded image file (PNG, JPG, etc.)

    Returns:
        OCRResponse: Contains extracted products and processing results

    Raises:
        HTTPException: If file type is invalid or processing fails
    """
    tmp_path = None

    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an image file (PNG, JPG, etc.)"
            )

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Extract products using OCR service
        catalog_result = ocr_service.extract_products(tmp_path)

        # Convert to response format
        products = [ProductResponse(**p.model_dump()) for p in catalog_result.products]

        # Save products to database
        save_results = []
        for product in catalog_result.products:
            save_result = database_service.save_product(product)
            save_results.append(ProcessingResult(
                status=save_result["status"],
                sku=save_result["sku"],
                error=save_result.get("error")
            ))

        # Calculate success metrics
        success_count = sum(1 for r in save_results if r.status == "success")

        # Generate user-friendly message
        success_status, message = message_service.generate_message(
            len(products), success_count
        )

        return OCRResponse(
            success=success_status,
            message=message,
            extracted_count=len(products),
            saved_count=success_count,
            products=products,
            results=save_results
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like validation errors)
        raise

    except Exception as e:
        # Handle unexpected errors gracefully
        return OCRResponse(
            success=False,
            message=f"An unexpected error occurred while processing the image: {str(e)}",
            extracted_count=0,
            saved_count=0,
            products=[],
            results=[]
        )

    finally:
        # Clean up temporary file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass  # Ignore cleanup errors


@app.get("/")
def root():
    """
    Root endpoint with API information.

    Returns:
        dict: Basic API information and usage links
    """
    return {
        "message": "Product OCR API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "POST /process-catalog": "Upload and process catalog image",
            "GET /health": "Health check",
            "GET /docs": "Interactive API documentation"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info"
    )