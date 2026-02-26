"""LLM / Run endpoints - completion proxy and BYOK key management."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.key_encryption import decrypt_api_key, encrypt_api_key
from app.db.session import get_db
from app.models.user import User
from app.models.user_llm_key import UserLLMKey
from app.services.llm_service import acompletion

router = APIRouter(prefix="/llm", tags=["llm"])


class CompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    stream: bool = False
    use_byok: bool = False


class SaveKeyRequest(BaseModel):
    provider: str
    api_key: str


class EstimateRequest(BaseModel):
    model: str
    messages: list[dict[str, str]] = []
    estimated_completion_tokens: int = 500


@router.post("/estimate")
async def estimate_cost(payload: EstimateRequest):
    """Estimate cost for platform-hosted run (before executing)."""
    try:
        import litellm
        prompt_tokens = 0
        if payload.messages:
            prompt_tokens = litellm.token_counter(model=payload.model, messages=payload.messages)
        else:
            prompt_tokens = 100  # default guess
        comp_tokens = payload.estimated_completion_tokens
        try:
            input_cost, output_cost = litellm.cost_per_token(
                model=payload.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
            )
            total = float(input_cost or 0) + float(output_cost or 0)
            return {
                "model": payload.model,
                "prompt_tokens": prompt_tokens,
                "estimated_completion_tokens": comp_tokens,
                "estimated_cost_usd": round(total, 6),
            }
        except Exception:
            return {
                "model": payload.model,
                "prompt_tokens": prompt_tokens,
                "estimated_completion_tokens": comp_tokens,
                "estimated_cost_usd": None,
                "message": "Cost data not available for this model",
            }
    except Exception as e:
        return {"error": str(e), "estimated_cost_usd": None}


@router.post("/keys")
async def save_llm_key(
    payload: SaveKeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save user's BYOK API key (encrypted at rest)."""
    provider = payload.provider.lower().strip()
    if provider not in ("openai", "anthropic"):
        raise HTTPException(400, "Provider must be openai or anthropic")
    if not payload.api_key or len(payload.api_key) < 10:
        raise HTTPException(400, "Invalid API key")
    encrypted = encrypt_api_key(payload.api_key)
    result = await db.execute(
        select(UserLLMKey).where(
            UserLLMKey.user_id == user.id,
            UserLLMKey.provider == provider,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.encrypted_key = encrypted
    else:
        db.add(UserLLMKey(user_id=user.id, provider=provider, encrypted_key=encrypted))
    await db.commit()
    return {"status": "saved"}


@router.delete("/keys/{provider}")
async def delete_llm_key(
    provider: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove user's BYOK key for provider."""
    result = await db.execute(
        select(UserLLMKey).where(
            UserLLMKey.user_id == user.id,
            UserLLMKey.provider == provider.lower(),
        )
    )
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    return {"status": "deleted"}


@router.get("/keys")
async def list_llm_key_providers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List providers for which user has BYOK key (no key values)."""
    result = await db.execute(
        select(UserLLMKey.provider).where(UserLLMKey.user_id == user.id)
    )
    return {"providers": [r[0] for r in result.all()]}


@router.post("/completion")
async def run_completion(
    payload: CompletionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run LLM completion. BYOK or platform key."""
    api_key = None
    if payload.use_byok:
        provider = payload.model.split("/")[0] if "/" in payload.model else "openai"
        result = await db.execute(
            select(UserLLMKey).where(
                UserLLMKey.user_id == user.id,
                UserLLMKey.provider == provider,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            api_key = decrypt_api_key(row.encrypted_key)
        else:
            raise HTTPException(400, f"No BYOK key saved for {provider}. Save your key first.")
    else:
        provider = payload.model.split("/")[0] if "/" in payload.model else "openai"
        key_attr = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(provider)
        if key_attr and not getattr(settings, key_attr, None):
            raise HTTPException(503, "Platform LLM key not configured. Use BYOK or set platform keys.")

    if payload.stream:
        async def gen():
            stream = await acompletion(
                model=payload.model,
                messages=payload.messages,
                api_key=api_key,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield f"data: {content}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    else:
        response = await acompletion(
            model=payload.model,
            messages=payload.messages,
            api_key=api_key,
            stream=False,
        )
        content = response.choices[0].message.content if response.choices else ""
        usage = getattr(response, "usage", None)
        usage_dict = None
        if usage:
            usage_dict = {"prompt_tokens": getattr(usage, "prompt_tokens", 0), "completion_tokens": getattr(usage, "completion_tokens", 0)}
        return {"content": content, "usage": usage_dict}
