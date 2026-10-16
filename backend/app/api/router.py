"""Main API router."""

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AirCreator Geometry & Reconstruction Engine",
        "version": "0.1.0",
    }
