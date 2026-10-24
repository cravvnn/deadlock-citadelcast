from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'preview-data.json').read_text())
# Keep full-rate evidence on disk. Embed a smaller, interpolated display series
# for the inline renderer's512KB document limit; this is not captured footage.
for series in [s['frames'] for s in data['shots']]+[data['obstruction']['frames']]:
    kept=series[::2]
    if kept[-1] is not series[-1]: kept.append(series[-1])
    series[:]=kept
def compact(v):
    if isinstance(v,float): return round(v,5)
    if isinstance(v,list): return [compact(x) for x in v]
    if isinstance(v,dict): return {k:compact(x) for k,x in v.items()}
    return v
data=compact(data)
data['obstruction']['full_frame_count']=601
template=(HERE/'preview_template.html').read_text(encoding='utf-8')
assert template.count('__DATA__')==1
html=template.replace('__DATA__',json.dumps(data,separators=(',',':')))
assert len(html) < 512000
(HERE/'camera-study.html').write_text(html,encoding='utf-8')
print(json.dumps({'file':str(HERE/'camera-study.html'),'bytes':len(html.encode('utf-8'))}))
