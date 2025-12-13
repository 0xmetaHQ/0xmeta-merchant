from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.startup import startup_checks, shutdown_handlers
from app.routes import news, config
import sys

# Setup logging
logger = setup_logging() 

# Create FastAPI app
app = FastAPI(
    title="0xMeta Crypto News Aggregator",
    description="Real-time crypto news aggregation API with category-based endpoints",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(news)
app.include_router(config)


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "0xmeta.ai",
        "description": "Real-time crypto news aggregation API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "OK"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": __import__("time").time()
    }


@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "name": "0xMeta Crypto News Aggregator",
        "version": "1.0.0",
        "status": "online",
        "endpoints": {
            "home": "/",
            "news": "/news/{category}",
            "categories": "/news/",
            "docs": "/docs",
            "openapi": "/openapi.json"
        },
        "pricing": {
            "per_request": "0.01 USDC",
            "network": settings.PAYMENT_NETWORK if hasattr(settings, 'PAYMENT_NETWORK') else "base-sepolia",
            "protocol": "X402"
        },
        "categories": [
            "btc", "eth", "sol", "base", "defi", "ai_agents", "rwa",
            "liquidity", "macro_events", "proof_of_work", "memecoins",
            "stablecoins", "nfts", "gaming", "launchpad", "virtuals", "trends", "other"
        ]
    }


@app.on_event("startup")
async def startup_event():
    """Run startup checks"""
    logger.info("=" * 70)
    logger.info("🚀 Starting 0xMeta Crypto News Aggregator API")
    logger.info("=" * 70)
    
    success = await startup_checks()
    if not success:
        logger.error("❌ Startup checks failed. Exiting...")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("✅ API is ready to accept requests")
    logger.info(f"📡 Listening on http://0.0.0.0:{settings.API_PORT}")
    logger.info(f"📚 API Docs: http://localhost:{settings.API_PORT}/docs")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Run shutdown handlers"""
    await shutdown_handlers()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.API_PORT,
        reload=settings.APP_ENV == "development",
        log_level=settings.LOG_LEVEL.lower()
    )