"""Bounded OFFLINE resource compilation. All source/output/write paths are in this lab."""
from pathlib import Path
import hashlib, json, shutil, subprocess

LAB = Path(__file__).resolve().parent
COMPILER = Path('D:/deadlock 3d/Reduced_CSDK_12/game/bin_cs2/win64/resourcecompiler.exe')
SDK = COMPILER.parents[3]
GAME = LAB/'compile/game/citadel'
CONTENT = LAB/'compile/content/citadel'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def bounded(p):
    p.resolve().relative_to(LAB)
    return p

if __name__ == '__main__':
    assert sha(COMPILER) == 'a0d3b34ec619c4a122d82ce2a8ff1517d6320519a5564923a607ce341ebc4201', 'offline compiler identity changed'
    bounded(GAME).mkdir(parents=True,exist_ok=True)
    # Explicit local Write path. No addon mounting or installed gameinfo mutation.
    config = '"GameInfo" { game "citadelcast_offline_ui" FileSystem { SearchPaths {\n'
    # Source2's filesystem rejected absolute Game paths in attempt01. Only these
    # read references cross the lab boundary; no output/source lives under them.
    assert (GAME.parent/'sdk-citadel').resolve() == (SDK/'game/citadel').resolve()
    assert (GAME.parent/'sdk-core').resolve() == (SDK/'game/core').resolve()
    for kind,p in [('Mod','citadel'),('Write','citadel'),('Game','citadel'),('GameBin','sdk-citadel/bin/win64'),('Game','sdk-citadel'),('Game','sdk-core')]:
        config += f'"{kind}" "{p}"\n'
    config += '} } }\n'
    (GAME/'gameinfo.gi').write_text(config)
    sources = sorted((LAB/'panorama').rglob('*'))
    report = {'offline_only':True,'compiler':str(COMPILER),'compiler_sha256':sha(COMPILER),'resources':[],'game_launched':False,'mounted':False}
    for source in sources:
        if not source.is_file(): continue
        relative = source.relative_to(LAB)
        target = bounded(CONTENT/relative)
        target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,target)
    for source in sources:
        if not source.is_file(): continue
        relative = source.relative_to(LAB)
        argv = [str(COMPILER),'-game',str(GAME),'-i',str(CONTENT/relative),'-nop4','-fshallow']
        result = subprocess.run(argv,cwd=LAB,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        log = LAB/('compile-'+source.name+'.log'); log.write_bytes(result.stdout+result.stderr)
        ext = {'.xml':'.vxml_c','.css':'.vcss_c','.js':'.vjs_c'}[source.suffix]
        output = bounded((GAME/relative).with_suffix(ext))
        row = {'source':relative.as_posix(),'source_sha256':sha(source),'argv':argv,'exit_code':result.returncode,'log':log.name,'output':str(output),'exists':output.is_file()}
        if output.is_file(): row['output_sha256']=sha(output)
        report['resources'].append(row)
        (LAB/'compile-review.json').write_text(json.dumps(report,indent=2))
        if result.returncode != 0 or not output.is_file():
            print(json.dumps(row)); raise SystemExit(1)
    print(json.dumps({'compiled':len(report['resources']),'game_launched':False,'mounted':False}))
