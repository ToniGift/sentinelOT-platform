import json
import os
import re
import time

from openai import APIConnectionError, APIStatusError, OpenAI

from config import NEBIUS_BASE_URL

client = OpenAI(base_url=NEBIUS_BASE_URL, api_key=os.environ["NEBIUS_API_KEY"],
                timeout=float(os.getenv("LLM_TIMEOUT_S", "60")), max_retries=0)
THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _create(**kw):
    """One model call with a single retry on timeouts, connection errors,
    rate limits (429) and server errors (5xx). Keeps the worst case for one
    call near twice the timeout instead of minutes."""
    for attempt in (0, 1):
        try:
            return client.chat.completions.create(**kw)
        except APIConnectionError:          # includes timeouts
            if attempt:
                raise
            time.sleep(1)
        except APIStatusError as e:
            if attempt or e.status_code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2)


def extract_json(text: str) -> dict:
    text = THINK.sub("", text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found (empty or truncated output)")
    return json.loads(text[start:end + 1])


def call_json(model, system, user, schema, temperature=0.2,
              max_tokens=4000, retries=1):
    """Call a Nebius model, parse JSON, validate against a Pydantic schema.
    Returns (validated_object, usage). Retries once with the error appended.
    max_tokens is generous because reasoning tokens count against it."""
    err = None
    for _ in range(retries + 1):
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        if err:
            msgs.append({"role": "user", "content":
                         f"Your previous reply was invalid: {err}. "
                         "Return only one valid JSON object."})
        r = _create(model=model, messages=msgs,
                    temperature=temperature, max_tokens=max_tokens)
        content = r.choices[0].message.content or ""
        try:
            return schema.model_validate(extract_json(content)), r.usage
        except Exception as e:
            err = str(e)[:300]
    raise RuntimeError(f"{model}: invalid output after retry: {err}")
