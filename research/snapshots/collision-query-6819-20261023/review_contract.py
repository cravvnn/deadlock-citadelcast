"""Bounded disk-only follow-up, importing the unchanged reviewed PE reader."""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'hero-framing-ab-6819-20261023'))
from review_adapter import Image

c = Image('client')  # Exact installed file hash, no process inspection.
functions = {hex(at): c.cfg(at, extent=8192) for at in (
    0x22b2b00, 0x5e9ef0, 0x94bc60, 0x17a37a0, 0x17b2d50, 0x265c30)}
sdk = HERE.parent / 'unlocker-mount-6817-20261022/sdk'
out = {
    'kind': 'pinned client disk and local SDK declarations; no native execution',
    'client_sha256': c.sha,
    'sdk_commit_from_existing_review': '7bba4bc8b8c0f7148835e5c6db0cbb97867852f9',
    'sdk_headers': {name: hashlib.sha256((sdk / 'public' / name).read_bytes()).hexdigest()
                    for name in ('ray.h', 'gametrace.h', 'mathlib/transform.h')},
    'functions': functions,
    'zero_vector_constructor_constant': list(c.read(0x2634b70, 12)),
    'native_runtime_binding_ready': False,
}
(HERE / 'disk-contract.json').write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps({k: v for k, v in out.items() if k != 'functions'}, indent=2))
