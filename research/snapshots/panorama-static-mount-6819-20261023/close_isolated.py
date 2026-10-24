"""Only AFTER normal operator close: archive/hash and remove exact ignored mod."""
from pathlib import Path
from datetime import datetime,timezone
import json
import startup_trial as s

def audit():
    if s.process_records():raise ValueError('Close Deadlock normally first; no cleanup/launch')
    s.validate_install();s.reviewed_artifact()
    old=s.HERE.parent/'panorama-static-watch-6819-20261023'
    run=Path(json.loads((old/'latest-run.json').read_text())['run_dir'])
    assert run.parent==old and run.name=='run-20261024_052614-cb8b1585891e5f31'
    j=json.loads((run/'journal.json').read_text())
    assert j['identity']['pid']==558400 and j['identity']['created']=='/Date(1792819576573)/'
    mount=Path(j['mod'])
    assert mount==s.GAME/'citadelcast_ui_cb8b1585891e5f31' and mount.resolve()==mount and not mount.is_symlink()
    config=s.INFO.read_bytes()
    assert s.sha(config)==s.STOCK_INFO,'Global configuration changed; preserve and review before retry'
    expected={mount/n for n in j['files']}
    assert {p for p in mount.rglob('*')}==expected,'Unknown inactive files; retain all and audit'
    assert all(p.resolve()==p and not p.is_symlink() and s.sha(p.read_bytes())==j['files'][p.name] for p in expected)
    out=run/('closed-before-normal-ui-'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'));out.mkdir(exist_ok=False)
    for p in expected:
        dest=out/p.name;dest.write_bytes(p.read_bytes());assert dest.read_bytes()==p.read_bytes()
    for name in ('process.stdout.log','process.stderr.log','asset-mount-failure-review.json'):
        data=(run/name).read_bytes();(out/name).write_bytes(data)
    log=s.GAME/'citadel/console.log'
    assert log.stat().st_size<=256*1024*1024
    (out/'console-final.log').write_bytes(log.read_bytes())
    (out/'preserved-current-gameinfo.gi').write_bytes(config)
    proof={'closed_owner_pid':558400,'process_absence_verified':True,'old_isolated_mount_removed':False,
           'global_config_original':True,'config_sha256':s.sha(config),'archive':str(out),
           'ui_test_started':False,'old_ui_package_actually_mounted':False,'exit_code':None,
           'steam_assertion_preserved':True,'prior_inactive4313_mount_retained':True}
    s.write_json(out/'review.json',proof)
    if s.process_records():raise ValueError('Game appeared; no inactive removal')
    assert s.INFO.read_bytes()==config
    for p in expected:assert p.read_bytes()==(out/p.name).read_bytes()
    for p in expected:p.unlink()
    mount.rmdir();assert not mount.exists() and s.INFO.read_bytes()==config
    proof['old_isolated_mount_removed']=True
    s.write_json(out/'review.json',proof);s.write_json(s.HERE/'parent-close-review.json',proof)
    print(json.dumps({'audit_passed':True,'old_isolated_mount_removed':True,'global_configuration_preserved':True,'archive':str(out)}))

if __name__=='__main__':audit()
