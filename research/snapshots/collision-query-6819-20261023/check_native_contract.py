"""Check explicit disk sites against the bounded declaration/consumer review.

This supplements, rather than replaces, manual data-flow review. It executes
neither the game nor its libraries. Failure must not refresh a build pin.
"""
from pathlib import Path
import hashlib
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'hero-framing-ab-6819-20261023'))
from review_adapter import Image
c=Image('client')
sites={
    0x17e5097:'mov r14, qword ptr [rbp + 0x2468]',
    0x17e50a1:'call 0x22b2b00',
    0x17e50ab:'movsd qword ptr [r14 + 0x78], xmm0',
    0x17e50c0:'movsd qword ptr [r14 + 0x84], xmm0',
    0x17e50d3:'movzx eax, byte ptr [rsi + 0x28]',
    0x17e50d7:'mov byte ptr [r14 + 0xba], al',
    0x17e50de:'cmp qword ptr [r12], 0',
    0x17e50e3:'je 0x17e5442',
    0x17e50f7:'mov r12, qword ptr [rbp + 0x2460]',
    0x17e50fe:'cmp byte ptr [r12 + 0x37], 1',
    0x17e5146:'cmp byte ptr [r12 + 0x40], 0',
    0x17e5426:'comiss xmm6, dword ptr [r14 + 0xac]',
    0x17e5438:'cmp byte ptr [r14 + 0xbb], 0',
    0x17e5442:'xor dil, dil',
    0x17e544c:'movzx eax, dil',
    0x22b2cd3:'mov dword ptr [rbp + 0xac], 0x3f800000',
    0x22b2cdd:'mov word ptr [rbp + 0xbb], r13w',
    0x22b2d47:'mov byte ptr [rbp + 0xba], r13b',
    0x17990f1:'mov dword ptr [rbx + 0xac], eax',
    0x17990fc:'mov byte ptr [rbx + 0xbb], al',
    0x5eff06:'call 0x17e4fe0',
    0x60f01b:'call 0x5eff80',
    0x6150d7:'call 0x60ed40',
}
for site,wanted in sites.items():
    i=c.ins(site);actual=f'{i.mnemonic} {i.op_str}'
    assert actual==wanted,(hex(site),actual,wanted)
assert c.read(0x2634b70,12)==bytes(12)
out={
    'kind':'pinned native instruction checks, not engine execution or live qualification',
    'client_sha256':c.sha,'instruction_sites_passed':len(sites),
    'zero_vector_constant_passed':True,
    'trace_entry_abi':{'rcx':'query holder','rdx':'Ray_t descriptor',
        'r8':'start XYZ','r9':'end XYZ','entry_rsp_plus_0x28':'CTraceFilter pointer',
        'entry_rsp_plus_0x30':'CGameTrace output pointer','return':'AL nonzero iff fraction<1 or start-solid; null-world returns false'},
    'stack_derivation':'seven pushes; RBP=entry_RSP-0x2438; +0x2460/+0x2468 therefore entry+0x28/+0x30',
    'runtime_binding_ready':False,
    'limits':['SDK field names corroborate layout but are not Valve API guarantees',
        'no whole-world lifetime, callback phase, layer semantics or live geometry qualification'],
    'sdk_probe_source_sha256':hashlib.sha256((HERE/'sdk_layout_probe.cpp').read_bytes()).hexdigest(),
}
(HERE/'native-contract-check.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
