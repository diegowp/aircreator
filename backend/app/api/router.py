"""Main API router."""

from fastapi import APIRouter

from app.api.endpoints.blueprint import router as blueprint_router
from app.api.endpoints.export import router as export_router
from app.api.endpoints.reconstruction import router as reconstruction_router

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

# 3D Reconstruction and Lofting endpoints
api_router.include_router(reconstruction_router)

# Export and Validation endpoints
api_router.include_router(export_router)
