"""Phase 0 smoke test.
Usage:
  python smoke_test.py                 # list models + test Tavily
  python smoke_test.py <model-id>      # also test one model for valid JSON
"""
import json, os, sys
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

load_dotenv()
for var in ("NEBIUS_API_KEY", "TAVILY_API_KEY"):
    if not os.getenv(var):
        sys.exit(f"Missing {var} in .env")

base = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
nb = OpenAI(base_url=base, api_key=os.environ["NEBIUS_API_KEY"])

print("== Nebius: models visible to this key ==")
ids = sorted(m.id for m in nb.models.list().data)
for i in ids:
    flag = "  <-- NVIDIA" if i.lower().startswith("nvidia/") else ""
    print(" ", i, flag)

if len(sys.argv) > 1:
    model = sys.argv[1]
    print(f"\n== Nebius: testing {model} ==")
    r = nb.chat.completions.create(
        model=model, max_tokens=1000, temperature=0.2,
        messages=[{"role": "user",
                   "content": 'Reply with only this JSON: {"ok": true}'}])
    content = r.choices[0].message.content
    print("content:", repr(content))
    print("usage:", r.usage)
    try:
        text = (content or "")
        obj = json.loads(text[text.find("{"): text.rfind("}") + 1])
        print("VALID JSON:", obj)
    except Exception as e:
        print("NOT valid JSON:", e, "(try a higher max_tokens)")

print("\n== Tavily ==")
tv = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
res = tv.search("CISA ICS advisory Modbus", max_results=2)
for x in res["results"]:
    print(" ", x["url"])
print("\nDone.")
