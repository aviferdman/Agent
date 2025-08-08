import time
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AzureOpenAI
from .config import settings
from .memory import build_memory

app = FastAPI(title="Engineering Assistant")

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("assistant")

AOAI_ENDPOINT = settings.azure_openai.endpoint
AOAI_KEY = settings.azure_openai.api_key
MODEL_NAME = settings.azure_openai.model
API_VERSION = settings.azure_openai.api_version

if not AOAI_KEY:
    LOGGER.warning("Azure OpenAI key not set. API calls will fail until provided.")

client = AzureOpenAI(
    api_key=AOAI_KEY,
    api_version=API_VERSION,
    azure_endpoint=AOAI_ENDPOINT
)

SYSTEM_PROMPT = (
    "You are an internal engineering assistant. Be concise. "
    "If clarification is needed, ask a question before answering."
)

memory_manager = build_memory(
    enabled=settings.memory.enabled,
    max_messages=settings.memory.max_messages,
    max_tokens=settings.memory.max_tokens
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = Field(None, description="Provide to enable memory if configured.")

@app.post("/chat")
async def chat(req: ChatRequest):
    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")

    use_memory = settings.memory.enabled and bool(req.session_id)
    history_messages = []
    if use_memory:
        try:
            history_messages = await memory_manager.get_history(req.session_id)  # type: ignore
        except Exception as e:
            LOGGER.exception("History retrieval failed: %s", e)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": msg})

    if use_memory:
        asyncio.create_task(memory_manager.add_message(req.session_id, "user", msg))  # type: ignore

    async def stream():
        assistant_chunks = []
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0.3,
                max_tokens=700,
                stream=True,
                messages=messages
            )
            for chunk in resp:
                try:
                    choices = getattr(chunk, 'choices', None)
                    if not choices:
                        continue
                    delta = getattr(choices[0], 'delta', None)
                    if not delta:
                        continue
                    delta_content = getattr(delta, 'content', None)
                    if delta_content:
                        assistant_chunks.append(delta_content)
                        yield delta_content
                except Exception as inner_e:
                    LOGGER.debug("Chunk parse issue: %s", inner_e)
                    continue
        except Exception as e:
            LOGGER.exception("Streaming error")
            yield f"\n[error] {e}"
        finally:
            if use_memory and assistant_chunks:
                try:
                    await memory_manager.add_message(req.session_id, "assistant", "".join(assistant_chunks))  # type: ignore
                except Exception as mem_e:
                    LOGGER.exception("Assistant turn store failed: %s", mem_e)

    return StreamingResponse(stream(), media_type="text/plain")


@app.get("/session/{session_id}")
async def session_snapshot(session_id: str):
    if not settings.memory.enabled:
        raise HTTPException(status_code=404, detail="Memory disabled")
    return await memory_manager.snapshot(session_id)  # type: ignore


@app.get("/config")
async def config_snapshot():
    return {
        "azure_openai": {
            "endpoint": settings.azure_openai.endpoint,
            "model": settings.azure_openai.model,
            "api_version": settings.azure_openai.api_version,
            "api_key_set": bool(settings.azure_openai.api_key)
        },
        "memory": {
            "enabled": settings.memory.enabled,
            "max_messages": settings.memory.max_messages,
            "max_tokens": settings.memory.max_tokens
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok", "time": int(time.time())}
