import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "triage"))
os.chdir(ROOT)
for k, v in {"NEBIUS_API_KEY": "test", "TAVILY_API_KEY": "test",
             "MODEL_INTAKE": "m", "MODEL_INTEL": "m", "MODEL_MAPPER": "m",
             "MODEL_TRIAGE": "m", "MODEL_ADVISOR": "m"}.items():
    os.environ.setdefault(k, v)
