"""Preserve console history and demand actual engine filesystem UI mount proof."""
from pathlib import Path
import hashlib,re

def sha(raw):return hashlib.sha256(raw).hexdigest()
def archive_before(path,run):
    path=Path(path)
    if not path.exists():return {'path':str(path),'archive':None,'bytes':0}
    if path.stat().st_size>256*1024*1024:raise ValueError('Console history exceeds bounded archive')
    raw=path.read_bytes();dest=Path(run)/'prelaunch-console.log';dest.write_bytes(raw)
    if dest.read_bytes()!=raw:raise ValueError('Console archive not exact')
    return {'path':str(path),'archive':str(dest),'bytes':len(raw),'sha256':sha(raw)}
def segment(path,before):
    p=Path(path)
    if not p.exists():return b'','not_emitted',0
    if p.stat().st_size>256*1024*1024:raise ValueError('Console exceeds bounded read')
    raw=p.read_bytes();offset=0;mode='created'
    if before['archive']:
        old=Path(before['archive']).read_bytes()
        if raw.startswith(old):offset=len(old);mode='appended'
        else:mode='engine_reset_or_rewrite'
    return raw[offset:],mode,offset
def filesystem_paths(text):
    return re.findall(r'\[Filesystem\]\s+GAME\s+"([^"\r\n]+)"',text)
def verify_mount(text,mount):
    normalize=lambda s:str(s).replace('\\','/').rstrip('/').lower()
    paths=filesystem_paths(text)
    expected=normalize(Path(mount)/'pak01.vpk')
    if expected not in [normalize(p) for p in paths]:
        raise ValueError('Engine filesystem did NOT mount exact UI VPK; argv/file existence are insufficient')
    return paths
def require_mount(path,mount,run,before):
    raw,mode,offset=segment(path,before);text=raw.decode('utf8',errors='replace')
    paths=verify_mount(text,mount)
    dest=Path(run)/'startup-console-ui-mount.log';dest.write_bytes(raw)
    return {'path':str(path),'archive':str(dest),'mode':mode,'offset':offset,'sha256':sha(raw),'filesystem_game_paths':paths,'exact_ui_vpk_mounted':True}
