"""Package only the three custom resources; independently decompile each with VRF."""
from pathlib import Path
import binascii, hashlib, json, struct, subprocess
from build_assets import LAB, GAME, sha

VIEWER = Path('D:/deadlock 3d/Deadlock_Next_Exports/Source2Viewer-CLI.exe')

def pack(payloads):
    tree = bytearray(); body = bytearray()
    groups = {}
    for name,payload in sorted(payloads.items()):
        p=Path(name); groups.setdefault(p.suffix[1:],{}).setdefault(p.parent.as_posix(),[]).append((p.stem,payload))
    for ext,folders in sorted(groups.items()):
        tree += ext.encode()+b'\0'
        for folder,files in sorted(folders.items()):
            tree += folder.encode()+b'\0'
            for name,payload in files:
                tree += name.encode()+b'\0'
                tree += struct.pack('<IHHIIH',binascii.crc32(payload)&0xffffffff,0,0x7fff,len(body),len(payload),0xffff)
                body += payload
            tree += b'\0'
        tree += b'\0'
    tree += b'\0'
    return struct.pack('<7I',0x55aa1234,2,len(tree),len(body),0,0,0)+tree+body

if __name__ == '__main__':
    review=json.loads((LAB/'compile-review.json').read_text())
    assert len(review['resources'])==3 and all(r['exit_code']==0 and r['exists'] for r in review['resources'])
    report={'independent_decompiler':str(VIEWER),'decompiler_sha256':sha(VIEWER),'roundtrips':[],'mounted':False,'live_verified':False}
    payloads={}
    for row in review['resources']:
        p=Path(row['output']); assert sha(p)==row['output_sha256']
        assert sha(LAB/row['source'])==row['source_sha256'], 'source changed since compilation'
        key=p.relative_to(GAME).as_posix(); assert key.startswith('panorama/') and '/citadelcast/' in key
        payloads[key]=p.read_bytes()
        out=LAB/'roundtrip'/p.suffix[1:]; out.mkdir(parents=True,exist_ok=True)
        # This installed CLI's -d writes beside the input despite -o. Give it a
        # private roundtrip copy, then demand the actual output before success.
        private_input=out/p.name; private_input.write_bytes(p.read_bytes())
        result=subprocess.run([str(VIEWER),'-i',str(private_input),'-d','-o',str(out)],cwd=LAB,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        log=LAB/('roundtrip-'+p.suffix[1:]+'.log'); log.write_bytes(result.stdout+result.stderr)
        ext={'.vxml_c':'.xml','.vcss_c':'.css','.vjs_c':'.js'}[p.suffix]
        output=out/(p.stem+ext)
        record={'compiled':key,'exit_code':result.returncode,'output_exists':output.is_file(),'log':log.name}
        report['roundtrips'].append(record)
        (LAB/'package-review.json').write_text(json.dumps(report,indent=2))
        assert result.returncode==0 and output.is_file(),record
        text=output.read_text(encoding='utf8')
        assert 'CitadelCastRecap' in text or 'RecapCard' in text
        record['output_sha256']=sha(output)
    packed=LAB/'citadelcast-recap-prototype_dir.vpk'; packed.write_bytes(pack(payloads))
    report['vpk']={'path':str(packed),'sha256':sha(packed),'bytes':packed.stat().st_size,'entries':{k:hashlib.sha256(v).hexdigest() for k,v in payloads.items()}}
    report['scope']='Three custom resources only. No stock HUD override, automatic load, native data bridge or delivery implementation.'
    (LAB/'package-review.json').write_text(json.dumps(report,indent=2))
    unpacked=LAB/'independent-unpack'; unpacked.mkdir(exist_ok=True)
    result=subprocess.run([str(VIEWER),'-i',str(packed),'-o',str(unpacked)],cwd=LAB,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    (LAB/'independent-unpack.log').write_bytes(result.stdout+result.stderr)
    assert result.returncode==0
    for key,payload in payloads.items():
        assert (unpacked/key).read_bytes()==payload, 'independent VPK extraction changed resource bytes'
    report['independent_vpk_extraction_exact']=True
    (LAB/'package-review.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'roundtrips':len(report['roundtrips']),'vpk_bytes':packed.stat().st_size,'mounted':False}))
