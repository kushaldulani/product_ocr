from fastapi import FastAPI
from app.api.routes import router
from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title="Product OCR API",
    version="1.0.0",
    description="AI-powered product information extraction from catalog images using Google Gemini Vision AI",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include API routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )