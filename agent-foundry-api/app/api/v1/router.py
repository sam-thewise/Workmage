"""API v1 router."""
from fastapi import APIRouter

from app.api.v1.endpoints import action_infra, admin, auth, agents, mcp, purchases, llm, runs, chains, experts

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(experts.router)
api_router.include_router(agents.router)
api_router.include_router(mcp.router)
api_router.include_router(purchases.router)
api_router.include_router(llm.router)
api_router.include_router(runs.router)
api_router.include_router(chains.router)
api_router.include_router(action_infra.router)
