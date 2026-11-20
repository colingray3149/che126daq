"""Small helpers shared by the other modules."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone


def iso(dt=None):
    return (dt or datetime.now(timezone.utc)).isoformat(timespec="milliseconds")


def fnum(v, digits=2):
    return "" if v is None or not math.isfinite(v) else "%.*f" % (digits, v)


def atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def deep_merge(base, extra):
    out = json.loads(json.dumps(base))
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def safe_name(name):
    name = re.sub(r"[^A-Za-z0-9 ._(),+-]", "", name or "").strip(" .")
    return name[:80] or "program"
