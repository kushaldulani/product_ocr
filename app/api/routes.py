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
        success_count = 0
        duplicate_count = 0
        variant_count = 0

        for product in result.products:
            save_result = save_product_to_db(product)

            # Track different statuses
            if save_result["status"] == "success":
                success_count += 1
                if save_result.get("variant_info"):
                    variant_count += 1
            elif save_result["status"] == "duplicate":
                duplicate_count += 1

            save_results.append(ProcessingResult(
                status=save_result["status"],
                sku=save_result.get("sku", product.sku),
                error=save_result.get("error") or save_result.get("variant_info")
            ))

        # Generate user-friendly messages
        if len(products) == 0:
            message = "No highlighted products found in the image. Please ensure products are clearly marked with circles, arrows, or other visual indicators."
            success = False
        else:
            message_parts = []
            message_parts.append(f"Identified {len(products)} product{'s' if len(products) != 1 else ''} from the catalog")

            if success_count > 0:
                if variant_count > 0:
                    message_parts.append(f"saved {success_count} ({variant_count} as variant{'s' if variant_count != 1 else ''})")
                else:
                    message_parts.append(f"saved {success_count}")

            if duplicate_count > 0:
                message_parts.append(f"{duplicate_count} already exist{'s' if duplicate_count == 1 else ''} in database")

            error_count = len(products) - success_count - duplicate_count
            if error_count > 0:
                message_parts.append(f"{error_count} failed")

            message = "Successfully " + ", ".join(message_parts) + "."
            success = True if success_count > 0 else False

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