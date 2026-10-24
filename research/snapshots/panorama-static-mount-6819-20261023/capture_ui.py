"""Owned normal-citadel static UI log proof, no console/control operations."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys
import startup_trial as s
import ui_logs

def capture(label):
    assert label and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in label)
    run=Path(json.loads((s.HERE/'latest-run.json').read_text())['run_dir']);assert run.parent==s.HERE
    j=json.loads((run/'journal.json').read_text());a=s.reviewed_artifact();s.validate_install()
    s.identity(j['identity']['pid'],None,j['identity']['created'])
    mount=Path(j['mount']);assert mount.resolve()==mount
    assert s.sha((mount/'pak01_dir.vpk').read_bytes())==a['ui_package_sha256']
    assert s.sha((mount/'bin/win64/server.dll').read_bytes())==a['dll_sha256']
    assert s.sha(s.INFO.read_bytes())==j['original_sha256'],'Preserve changed global config; do not overwrite'
    raw,mode,offset=ui_logs.segment(s.GAME/'citadel/console.log',j['console_baseline'])
    text=raw.decode('utf8',errors='replace');paths=ui_logs.verify_mount(text,mount)
    folder=run/(label+'-'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'));folder.mkdir(exist_ok=False)
    (folder/'console-session.log').write_bytes(raw)
    markers=[line for line in text.splitlines() if '[CitadelCastUI:STATIC:v1]' in line]
    diagnostic=[line for line in text.splitlines() if any(t in line.lower() for t in ('assertion failed','static_probe','javascript error','referenceerror','typeerror','syntaxerror'))]
    result={'identity':j['identity'],'exact_ui_vpk_mounted':True,'filesystem_game_paths':paths,'mode':mode,'offset':offset,
       'ui_markers':markers,'static_12s_script_complete':any('ended reason=complete_12s' in line for line in markers),
       'diagnostic_lines':diagnostic[-80:],'global_config_original':True,'engine_visual_result_operator_confirmed':False}
    s.write_json(folder/'review.json',result);s.write_json(run/'latest-ui-capture.json',{'review':str(folder/'review.json')})
    print(json.dumps({k:result[k] for k in ('exact_ui_vpk_mounted','ui_markers','static_12s_script_complete','global_config_original')}))

if __name__=='__main__':capture(sys.argv[1])
