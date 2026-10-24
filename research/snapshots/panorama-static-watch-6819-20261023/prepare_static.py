"""Author one additive diagnostic in the exact native6819 HUD. OFFLINE only."""
from pathlib import Path
import copy,hashlib,json,shutil,xml.etree.ElementTree as ET

LAB=Path(__file__).resolve().parent
PARENT=LAB.parent/'panorama-broadcast-6819-20261023'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def structural(n):return (n.tag,sorted(n.attrib.items()),(n.text or '').strip(),[structural(c) for c in n])

if __name__=='__main__':
    raw=LAB/'native/hud.vxml_c'
    assert sha(raw)=='09789089d6dacad40324437af7f8229138605eec8ed7fdf1bd87df37b01944fa'
    stock=ET.fromstring((LAB/'native/hud.xml').read_text(encoding='utf8'))
    candidate=copy.deepcopy(stock)
    styles=candidate.find('styles')
    ET.SubElement(styles,'include',{'src':'file://{resources}/styles/citadelcast/static_probe.css'})
    scripts=ET.Element('scripts');ET.SubElement(scripts,'include',{'src':'file://{resources}/scripts/citadelcast/static_probe.js'})
    candidate.insert(1,scripts)
    hud=candidate.find('CitadelHud');assert hud is not None
    probe=ET.SubElement(hud,'Panel',{'id':'CitadelCastStaticProbe','class':'CitadelCastStaticProbe','hittest':'false','hittestchildren':'false'})
    card=ET.SubElement(probe,'Panel',{'class':'CCStaticCard'})
    ET.SubElement(card,'Label',{'class':'CCStaticTitle','text':'CITADELCAST — UI TEST','html':'false'})
    ET.SubElement(card,'Label',{'class':'CCStaticSample','text':'SAMPLE · NOT LIVE PLAYER DATA','html':'false'})
    row=ET.SubElement(card,'Panel',{'class':'CCStaticMetrics'})
    for value,label,icon in [('2','KILLS','post_game/attributes/icon_kill.vsvg'),('3','ASSISTS',None),('+3,200','SOULS EARNED','hud/icons/icon_souls.vsvg')]:
        metric=ET.SubElement(row,'Panel',{'class':'CCStaticMetric'})
        if icon:ET.SubElement(metric,'Image',{'class':'CCStaticIcon','src':'s2r://panorama/images/'+icon})
        ET.SubElement(metric,'Label',{'class':'CCStaticValue','text':value,'html':'false'})
        ET.SubElement(metric,'Label',{'class':'CCStaticLabel','text':label,'html':'false'})
    ET.SubElement(card,'Label',{'class':'CCStaticFooter','text':'Native HUD retained · closes automatically','html':'false'})
    restored=copy.deepcopy(candidate)
    restored.find('styles').remove(list(restored.find('styles'))[-1])
    restored.remove(restored.find('scripts'))
    restored.find('CitadelHud').remove(restored.find('CitadelHud/Panel[@id="CitadelCastStaticProbe"]'))
    assert structural(restored)==structural(stock),'Native HUD structure changed beyond owned additions'
    path=LAB/'panorama/layout/hud.xml';path.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(candidate,space='\t');path.write_text(ET.tostring(candidate,encoding='unicode')+'\n',encoding='utf8')
    shutil.copyfile(PARENT/'build_assets.py',LAB/'build_assets.py')
    report={'native_hud_sha256':sha(raw),'source_sha256':sha(path),'stock_tree_after_removing_additions_exact':True,
        'original_root_attributes_unchanged':True,'stock_callbacks_bindings_ids_unchanged':True,
        'added_resources':['panorama/layout/hud.vxml_c','panorama/styles/citadelcast/static_probe.vcss_c','panorama/scripts/citadelcast/static_probe.vjs_c'],
        'live_render_verified':False,'automatic_camera_or_console_commands':False}
    (LAB/'host-review.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
