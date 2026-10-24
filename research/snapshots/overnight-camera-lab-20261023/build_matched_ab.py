from pathlib import Path
import json, hashlib, math
HERE=Path(__file__).resolve().parent
source=HERE.parent/'hero-framing-ab-6819-20261023'
data=json.loads((HERE/'matched-ab.json').read_text())
frames=data['frames']
assert len(frames)==961 and data['game_access'] is False
assert all(math.isfinite(v) for f in frames for a in f.values() for v in (a if isinstance(a,list) else [a]))
assert all(abs(f['b_desired_bearing']-45)<1e-9 for f in frames)
assert frames[-1]['a_desired_bearing']-frames[-1]['b_desired_bearing']>150
review=json.loads((source/'candidate-review.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=review['source_manifest']
for name,expected in manifest.items():
    assert sha(source/'source'/name)==expected,(name,'accepted A/B file changed')
html=(HERE/'matched_ab_template.html').read_text(encoding='utf-8').replace('__DATA__',json.dumps(data,separators=(',',':')))
assert len(html.encode())<512000
(HERE/'matched-ab.html').write_text(html,encoding='utf-8')
result={'kind':'synthetic matched input, accepted immutable rig code','samples':len(frames),'duration':8,'entry_included':False,'game_access':False,'source_files_verified':len(manifest),'final_a_desired_bearing':frames[-1]['a_desired_bearing'],'final_b_desired_bearing':frames[-1]['b_desired_bearing'],'html_bytes':len(html.encode()),'files':{n:sha(HERE/n) for n in ['native/hero_ab_sim.cpp','native/CMakeLists.txt','native-build/Release/hero_ab_sim.exe','matched-ab.json','matched-ab.html']}}
(HERE/'matched-ab-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'}))
