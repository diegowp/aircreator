"""Main API router."""

from fastapi import APIRouter

from app.api.endpoints.blueprint import router as blueprint_router

api_router = APIRouter()

# System endpoints
@api_router.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AirCreator Geometry & Reconstruction Engine",
        "version": "0.1.0",
    }

# Blueprint CV and Calibration endpoints
api_router.include_router(blueprint_router)
