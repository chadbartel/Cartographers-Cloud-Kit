# Third Party
from fastapi import APIRouter

# Local Modules
from api_backend.routers import assets

# Create a router instance with a default prefix
router = APIRouter()

# Include other routers
router.include_router(assets.router)
