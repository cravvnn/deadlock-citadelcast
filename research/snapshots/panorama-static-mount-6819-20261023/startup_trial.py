"""One reversible owned Walker viewer startup; adapter stays idle for operator start."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import ui_logs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

GAME = Path('B:/SteamLibrary/steamapps/common/Deadlock/game')
EXE = GAME/'bin/win64/deadlock.exe'
INFO = GAME/'citadel/gameinfo.gi'
DLL = HERE/'build/Release/server.dll'
CARRIER = HERE/'walker-shot.kv'
# Legacy constant name: this is the EXACT reviewed CURRENT Modlock config, not
# a claim of stock bytes. CAS restores this same current file after registration.
STOCK_INFO = '482846ad152fecdd1331b09321bb7d28af2e4bb5600035292a976a8c881f185d'
PINS = {
    'bin/win64/deadlock.exe': '69ce101f58cf0b784f5f5453781120613e780dc1ee8f1f07a73bbcbf4381be7b',
    'citadel/bin/win64/client.dll': 'c09143cf9cd722909404c64e3ffa05157afc15e8a3519b49a1396a627af8ca85',
    'citadel/bin/win64/server.dll': '4855ef0712962f43aa4d9f623b258ada286d3e6f8fd2a2c8272984bfecf777e8',
    'bin/win64/tier0.dll': '666c9022739190d571a67161646d1a55511e130b62c3a93f8c95b47beaede433',
    'bin/win64/engine2.dll': 'f7dd5763050e203361809360b4354ef3f768753bb6e43fb314d4822065d28da6',
    'bin/win64/networksystem.dll': '5483a9b5a02a16d98431b89b8f2604f5511d37ddd4a396a608ced1d7ce946eef',
}

def sha(data): return hashlib.sha256(data).hexdigest()
def write_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,path)
def progress(phase, **fields):
    print(json.dumps({'phase':phase,**fields}),flush=True)
def powershell(script):
    result=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,
                          timeout=12,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(result.stdout) if result.stdout.strip() else None
def process_records():
    value=powershell("Get-CimInstance Win32_Process -Filter \"Name='deadlock.exe' OR Name='citadel.exe'\" | Select-Object ProcessId,ExecutablePath,CreationDate,CommandLine | ConvertTo-Json -Compress")
    return value if isinstance(value,list) else [value] if value else []
def tokens(command):
    api=ctypes.WinDLL('shell32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CommandLineToArgvW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)]
    api.CommandLineToArgvW.restype=ctypes.POINTER(wintypes.LPWSTR)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    count=ctypes.c_int()
    pointer=api.CommandLineToArgvW(command,ctypes.byref(count))
    if not pointer: raise OSError('Could not decode owned process arguments')
    try: return [pointer[i] for i in range(count.value)]
    finally: kernel.LocalFree(pointer)
def validate_arguments(args, exe, port):
    expected=[str(exe),'-game','citadel','-dev','-insecure','-console','-condebug']
    if port is not None: raise ValueError('This reviewed startup has no console transport')
    if len(args)!=len(expected) or Path(args[0]).resolve()!=exe.resolve() or args[1:]!=expected[1:]:
        raise ValueError('Owned process does not have the exact reviewed arguments')
def identity(pid, port, created=None):
    rows=process_records()
    if len(rows)!=1 or int(rows[0]['ProcessId'])!=pid: raise ValueError('Game ownership became ambiguous')
    row=rows[0]
    if Path(row['ExecutablePath']).resolve()!=EXE.resolve(): raise ValueError('Wrong owned executable')
    validate_arguments(tokens(row['CommandLine']), EXE, port)
    if created is not None and row['CreationDate']!=created: raise ValueError('Owned process identity changed')
    return {'pid':pid,'created':row['CreationDate'],'executable':str(EXE),'dev':True,'insecure':True,'port':port}
def mounted_bytes(original, mount_name):
    if not re.fullmatch(r'citadelcast_walker_[0-9a-f]{16}',mount_name): raise ValueError('Invalid owned mount name')
    pattern=rb'(?m)^([\t ]*)Game[\t ]+citadel[\t ]*(\r?\n)'
    found=list(re.finditer(pattern,original))
    if len(found)!=1: raise ValueError('Expected one unmodified base Game search path')
    first=re.search(rb'(?m)^([\t ]*)Game[\t ]+[^\r\n]+(\r?\n)',original)
    if not first: raise ValueError('No ordinary Game search path')
    match=first;indent=match[1];newline=match[2]
    additions=indent+b'Mod\t\tcitadel'+newline+indent+b'Write\t\tcitadel'+newline
    additions+=indent+b'Game\t\tcitadel/'+mount_name.encode('ascii')+newline
    return original[:match.start()]+additions+original[match.start():]
def replace_exact(path, before, after):
    if path.read_bytes()!=before: raise ValueError('Configuration changed externally; refusing overwrite')
    temporary=path.with_name(path.name+'.citadelcast-'+secrets.token_hex(8)+'.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(after);stream.flush();os.fsync(stream.fileno())
        if path.read_bytes()!=before: raise ValueError('Configuration changed during preparation')
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()
def restore_exact(path, mounted, original):
    current=path.read_bytes()
    if current==original: return 'already_original'
    if current!=mounted: raise ValueError('Configuration restoration conflict; backup retained')
    replace_exact(path,mounted,original)
    if path.read_bytes()!=original: raise ValueError('Configuration restoration verification failed')
    return 'restored_exactly'
def validate_install(game=GAME):
    for relative,expected in PINS.items():
        if sha((game/relative).read_bytes())!=expected: raise ValueError('Unreviewed game file: '+relative)
    inf=dict(line.split('=',1) for line in (game/'citadel/steam.inf').read_text().splitlines() if '=' in line)
    if inf.get('ClientVersion')!='6819' or inf.get('ServerVersion')!='6819': raise ValueError('Unreviewed game version')
    return inf
def carrier_manifest(artifact):
    values=artifact.get('carriers',{'walker-shot.kv':artifact['carrier_sha256']})
    if not isinstance(values,dict) or not values or values.get('walker-shot.kv')!=artifact['carrier_sha256']:
        raise ValueError('Invalid reviewed camera manifest')
    for name,digest in values.items():
        if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,48}\.kv',name):
            raise ValueError('Invalid reviewed camera filename')
        if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):
            raise ValueError('Invalid reviewed camera digest')
    return values

def carrier_source(name):
    return CARRIER if name=='walker-shot.kv' else HERE/name

def reviewed_artifact():
    review=json.loads((HERE/'candidate-review.json').read_text())
    if not review['offline_qualified_for_bounded_startup']: raise ValueError('Candidate review incomplete')
    if sha(Path(__file__).read_bytes())!=review['harness_sha256']: raise ValueError('Reviewed startup harness changed')
    if sha(DLL.read_bytes())!=review['dll_sha256']: raise ValueError('Candidate DLL changed')
    if sha((HERE/'ui-test_dir.vpk').read_bytes())!=review['ui_package_sha256']: raise ValueError('Reviewed UI package changed')
    for name,digest in carrier_manifest(review).items():
        if sha(carrier_source(name).read_bytes())!=digest: raise ValueError('Candidate camera data changed: '+name)
    for name,expected in review['source_manifest'].items():
        if sha((HERE/'source'/name).read_bytes())!=expected: raise ValueError('Reviewed source changed')
    for name,expected in review.get('extra_manifest',{}).items():
        if Path(name).is_absolute() or '..' in Path(name).parts or sha((HERE/name).read_bytes())!=expected:
            raise ValueError('Reviewed UI helper changed: '+name)
    return review
def cleanup_inactive_mount(mount, dll_hash, carrier_hash, carriers=None,ui_hash=None):
    parent=(GAME/'citadel').resolve()
    resolved=mount.resolve()
    if resolved.parent!=parent or not re.fullmatch(r'citadelcast_walker_[0-9a-f]{16}',resolved.name):
        raise ValueError('Refusing cleanup outside this owned mount')
    binary=resolved/'bin/win64/server.dll'
    carriers=carrier_manifest({'carrier_sha256':carrier_hash,**({'carriers':carriers} if carriers is not None else {})})
    paths=[resolved/name for name in carriers]
    statuses=[resolved/'bin/win64'/name for name in ('server.dll.status.json','server.dll.status.json.tmp','server.dll.walker-status.json','server.dll.walker-status.json.tmp')]
    allowed=set(paths+[binary]+statuses+[resolved/'bin',resolved/'bin/win64'])
    ui=resolved/'pak01_dir.vpk'
    if ui_hash is not None: allowed.add(ui)
    if any(path.is_symlink() or path.resolve()!=path for path in allowed):
        raise ValueError('Owned path redirects elsewhere; retaining files')
    if any(path not in allowed for path in resolved.rglob('*')):
        raise ValueError('Unexpected owned mount entry; retaining files')
    for path in paths:
        if path.exists() and sha(path.read_bytes())!=carriers[path.name]:
            raise ValueError('Owned camera data changed; retaining files')
    if ui_hash is not None and ui.exists() and sha(ui.read_bytes())!=ui_hash:
        raise ValueError('Owned UI package changed; retaining files')
    if binary.exists():
        if sha(binary.read_bytes())!=dll_hash: raise ValueError('Owned plugin changed; retaining files')
        binary.unlink()
    for path in paths+statuses:
        if path.exists(): path.unlink()
    if ui_hash is not None and ui.exists(): ui.unlink()
    for path in (resolved/'bin/win64',resolved/'bin',resolved): path.rmdir()

def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch-once',action='store_true')
    parser.add_argument('--manual-console',action='store_true',help='Hand the registered viewer to the operator without any console connection or commands')
    parser.add_argument('--watch-seconds',type=int,default=0,choices=(0,))
    args=parser.parse_args()
    if not args.manual_console or args.watch_seconds!=0:
        raise ValueError('Walker startup requires --manual-console --watch-seconds 0; no automated console or camera commands')
    if not args.launch_once: raise ValueError('Explicit --launch-once is required')
    inf=validate_install();artifact=reviewed_artifact()
    if process_records(): raise ValueError('A game is already running; no mount or attachment performed')
    carriers=carrier_manifest(artifact)
    original=INFO.read_bytes()
    if sha(original)!=STOCK_INFO: raise ValueError('Reviewed current gameinfo changed; preserve external setup and review before mounting')
    nonce=secrets.token_hex(8)
    run_dir=HERE/('run-'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'-'+nonce)
    run_dir.mkdir()
    (run_dir/'original.gameinfo.gi').write_bytes(original)
    harness=Path(__file__).read_bytes()
    (run_dir/'startup_trial.py').write_bytes(harness)
    (run_dir/'candidate-review.json').write_bytes((HERE/'candidate-review.json').read_bytes())
    mount_name='citadelcast_walker_'+nonce
    mount=GAME/'citadel'/mount_name
    mounted=mounted_bytes(original,mount_name)
    process=None;owned=None;mount_written=False;deployment_created=False
    journal={'scope':'one owned startup with idle Walker adapter; operator joins Watch and starts off-air manually',
             'build':inf,'run_dir':str(run_dir),'mount':str(mount),'original_sha256':sha(original),
             'mounted_sha256':sha(mounted),'dll_sha256':artifact['dll_sha256'],'carrier_sha256':artifact['carrier_sha256'],'phase':'prepared'}
    journal['carriers']=carriers
    journal['harness_sha256']=sha(harness)
    journal['verification_mode']='manual_console'
    journal['console_logging_requested']=True
    journal['console_logging_observed']=False
    journal['ui_package_sha256']=artifact['ui_package_sha256']
    journal['console_baseline']=ui_logs.archive_before(GAME/'citadel/console.log',run_dir)
    def save(): write_json(run_dir/'journal.json',journal)
    save();write_json(HERE/'latest-run.json',{'run_dir':str(run_dir)})
    try:
        (mount/'bin/win64').mkdir(parents=True,exist_ok=False)
        deployment_created=True
        shutil.copyfile(DLL,mount/'bin/win64/server.dll')
        shutil.copyfile(HERE/'ui-test_dir.vpk',mount/'pak01_dir.vpk')
        if sha((mount/'pak01_dir.vpk').read_bytes())!=artifact['ui_package_sha256']: raise ValueError('UI deployment mismatch')
        for name,digest in carriers.items():
            with (mount/name).open('xb') as stream: stream.write(carrier_source(name).read_bytes())
            if sha((mount/name).read_bytes())!=digest: raise ValueError('Camera data deployment mismatch: '+name)
        if sha((mount/'bin/win64/server.dll').read_bytes())!=artifact['dll_sha256']: raise ValueError('Deployment hash mismatch')
        if process_records(): raise ValueError('A game appeared before mounting; refusing startup')
        validate_install()
        journal['phase']='mount_pending';save()
        replace_exact(INFO,original,mounted);mount_written=True
        journal['phase']='mounted';save()
        port=None
        arguments=[str(EXE),'-game','citadel','-dev','-insecure','-console','-condebug']
        validate_arguments(arguments,EXE,port)
        if process_records(): raise ValueError('A game appeared immediately before launch')
        with (run_dir/'process.stdout.log').open('wb') as stdout, (run_dir/'process.stderr.log').open('wb') as stderr:
            process=subprocess.Popen(arguments,cwd=EXE.parent,stdout=stdout,stderr=stderr)
        journal['pid']=process.pid;journal['phase']='launched';save()
        owned=identity(process.pid,port);journal['identity']=owned;save()
        progress('owned_flags_verified',pid=process.pid,dev=True,insecure=True,run_dir=str(run_dir))
        deadline=time.monotonic()+100
        status_path=mount/'bin/win64/server.dll.status.json'
        while time.monotonic()<deadline:
            if process.poll() is not None: raise ValueError('Owned game exited during startup: '+str(process.returncode))
            identity(process.pid,port,owned['created'])
            if status_path.exists():
                try: status=json.loads(status_path.read_text())
                except (ValueError,OSError): status={}
                if status.get('pid')==process.pid and status.get('phase')=='registered' and status.get('walker_commands_registered') is True:
                    journal['plugin_status']=status;break
            time.sleep(1)
        else: raise TimeoutError('No plugin registration acknowledgement within the one startup attempt')
        progress('plugin_registered',pid=process.pid)
        journal['ui_asset_mount']=ui_logs.require_mount(GAME/'citadel/console.log',mount,run_dir,journal['console_baseline'])
        journal['console_logging_observed']=True
        progress('ui_asset_mount_verified',pid=process.pid)
        journal['gameinfo_restoration']=restore_exact(INFO,mounted,original)
        mount_written=False;journal['phase']='registered_mount_restored';save()
        identity(process.pid,None,owned['created'])
        journal['phase']='handed_to_operator_manual_console'
        journal['automated_camera_started']=False
        journal['watch_broadcast_observed']=False
        save()
        progress('handed_to_operator_manual_console',pid=process.pid,gameinfo_restored=True,
                 plugin_registered=True,dev=True,insecure=True,run_dir=str(run_dir))
    except BaseException as exc:
        journal['error']=str(exc);journal['phase']='failed';save();progress('failed',error=str(exc))
        if process is not None and process.poll() is None and owned is not None:
            try:
                identity(process.pid,owned['port'],owned['created'])
                if process.poll() is None:
                    identity(process.pid,owned['port'],owned['created'])
                    process.terminate();process.wait(timeout=8)
                    journal['bounded_failure_terminated_owned_process']=True
            except Exception as cleanup_error: journal['process_cleanup_error']=str(cleanup_error)
        raise
    finally:
        try: current_info=INFO.read_bytes()
        except OSError as read_error:
            current_info=None;journal['configuration_read_error']=str(read_error)
        if mount_written or current_info==mounted:
            try: journal['gameinfo_restoration']=restore_exact(INFO,mounted,original)
            except Exception as restore_error: journal['restoration_error']=str(restore_error)
        if deployment_created and (process is None or process.poll() is not None):
            try: cleanup_inactive_mount(mount,artifact['dll_sha256'],artifact['carrier_sha256'],carriers,artifact['ui_package_sha256']);journal['inactive_mount_removed']=True
            except Exception as cleanup_error: journal['mount_cleanup_error']=str(cleanup_error)
        elif process is not None and process.poll() is None: journal['inactive_files_retained_for_running_viewer']=True
        try: journal['final_gameinfo_sha256']=sha(INFO.read_bytes())
        except OSError as read_error:
            journal['final_gameinfo_sha256']=None;journal['configuration_read_error']=str(read_error)
        save()
        if process is not None: journal['final_exit_code']=process.poll()
        write_json(run_dir/'result.json',journal)
        progress('settled',gameinfo_original=journal['final_gameinfo_sha256']==sha(original),
                 automated_camera_started=False,manual_console_pending=True)

if __name__=='__main__': run()
