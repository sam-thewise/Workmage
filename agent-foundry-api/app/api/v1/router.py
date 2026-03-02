"""API v1 router."""
from fastapi import APIRouter

from app.api.v1.endpoints import action_infra, admin, auth, agents, content_drafts, mcp, mcp_github, personality, purchases, llm, runs, chains, experts, saved_outputs, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(experts.router)
api_router.include_router(agents.router)
api_router.include_router(mcp_github.router)
api_router.include_router(mcp.router)
api_router.include_router(purchases.router)
api_router.include_router(llm.router)
api_router.include_router(runs.router)
api_router.include_router(chains.router)
api_router.include_router(content_drafts.router)
api_router.include_router(personality.router)
api_router.include_router(saved_outputs.router)
api_router.include_router(action_infra.router)
