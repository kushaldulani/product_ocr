from fastapi import APIRouter, File, UploadFile, HTTPException
import tempfile
import os
from app.models.schemas import OCRResponse, ProductResponse, ProcessingResult, HealthResponse
from app.services.ocr_service import extract_products, save_product_to_db

router = APIRouter()

@router.post("/process-catalog", response_model=OCRResponse)
async def process_catalog_image(file: UploadFile = File(...)):
    """Process catalog image and save products to database"""
    tmp_path = None

    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Extract products from image
        result = extract_products(tmp_path)
        products = [ProductResponse(**p.model_dump()) for p in result.products]

        # Save to database
        save_results = []
        for product in result.products:
            save_result = save_product_to_db(product)
            save_results.append(ProcessingResult(
                status=save_result["status"],
                sku=save_result["sku"],
                error=save_result.get("error")
            ))

        success_count = sum(1 for r in save_results if r.status == "success")

        # Generate user-friendly messages
        if len(products) == 0:
            message = "No highlighted products found in the image. Please ensure products are clearly marked with circles, arrows, or other visual indicators."
            success = False
        elif success_count == 0:
            message = f"Successfully identified {len(products)} product{'s' if len(products) != 1 else ''} from the catalog, but encountered database issues while saving. All products may already exist or there are connectivity problems."
            success = True
        elif success_count == len(products):
            message = f"Perfect! Successfully identified and saved {len(products)} product{'s' if len(products) != 1 else ''} to the database."
            success = True
        else:
            message = f"Successfully identified {len(products)} product{'s' if len(products) != 1 else ''} from the catalog and saved {success_count} to the database. {len(products) - success_count} product{'s' if (len(products) - success_count) != 1 else ''} may already exist in the database."
            success = True

        return OCRResponse(
            success=success,
            message=message,
            extracted_count=len(products),
            saved_count=success_count,
            products=products,
            results=save_results
        )

    except HTTPException:
        raise
    except Exception as e:
        return OCRResponse(
            success=False,
            message=f"Error processing image: {str(e)}",
            extracted_count=0,
            saved_count=0,
            products=[],
            results=[]
        )

    finally:
        # Clean up temporary file if it was created
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="Product OCR API",
        version="1.0.0"
    )


@router.get("/")
def root():
    """API information and documentation links"""
    return {
        "service": "Product OCR API",
        "version": "1.0.0",
        "description": "AI-powered product information extraction from catalog images",
        "docs": "/docs",
        "health": "/health"
    }