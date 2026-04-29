"""Dashboard API routes - system status, metrics, and security data."""
from fastapi import APIRouter
from ..services.dashboard_service import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/health")
async def get_health():
    """Get system health status."""
    return dashboard_service.get_health()


@router.get("/metrics")
async def get_metrics():
    """Get request metrics."""
    return dashboard_service.get_metrics()


@router.get("/features")
async def get_features():
    """Get security features list."""
    return dashboard_service.get_features()


@router.get("/pipeline")
async def get_pipeline():
    """Get the output security pipeline phases."""
    return dashboard_service.get_pipeline()


@router.get("/issues")
async def get_issues():
    """Get known issues categorized by severity."""
    return dashboard_service.get_issues()


@router.get("/codebase-stats")
async def get_codebase_stats():
    """Get codebase statistics."""
    return dashboard_service.get_codebase_stats()


@router.get("/components")
async def get_components():
    """Get component inventory."""
    return dashboard_service.get_components()


@router.get("/roadmap")
async def get_roadmap():
    """Get improvement roadmap."""
    return dashboard_service.get_roadmap()
