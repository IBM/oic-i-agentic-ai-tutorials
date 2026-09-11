import os

import torch
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = os.getenv("MODEL_NAME", "ibm-granite/granite-4.0-h-1b")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")  # simple bearer

app = FastAPI(title="Granite Nano OpenAI-compatible API")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = 256
    temperature: float | None = 0.3
    top_p: float | None = 0.95
    stream: bool | None = False


@app.middleware("http")
async def auth(request: Request, call_next):
    if AUTH_TOKEN:
        header = request.headers.get("authorization", "")
        if header != f"Bearer {AUTH_TOKEN}":
            raise HTTPException(status_code=401, detail="Unauthorized")
    return await call_next(request)


@app.post("/v1/chat/completions")
async def chat(req: ChatRequest):
    # build a simple chat prompt
    parts: list[str] = []
    for m in req.messages:
        prefix = (
            "User:"
            if m.role == "user"
            else ("Assistant:" if m.role == "assistant" else "System:")
        )
        parts.append(f"{prefix} {m.content}")
    parts.append("Assistant:")
    prompt = "\n".join(parts)

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=req.max_tokens or 256,
        do_sample=True,
        temperature=req.temperature or 0.3,
        top_p=req.top_p or 0.95,
        pad_token_id=tokenizer.eos_token_id,
    )
    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # return only the assistant tail
    assistant_text = text.split("Assistant:")[-1].strip()

    return {
        "id": "chatcmpl-granite-nano",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": assistant_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(inputs.input_ids[0]),
            "completion_tokens": len(outputs[0]),
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}
