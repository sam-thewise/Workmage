"""API v1 router."""
from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, agents, purchases, llm, runs, chains, experts

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(experts.router)
api_router.include_router(agents.router)
api_router.include_router(purchases.router)
api_router.include_router(llm.router)
api_router.include_router(runs.router)
api_router.include_router(chains.router)
