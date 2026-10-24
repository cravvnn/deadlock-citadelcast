"""Read-only evidence snapshot of this exact owned follow viewer."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import re
import shutil
import startup_trial as startup
from take_records import snapshot as snapshot_takes

HERE=Path(__file__).resolve().parent

def capture():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label');parser.add_argument('--screenshot',type=Path)
    args=parser.parse_args();assert re.fullmatch(r'[a-z0-9-]{1,48}',args.label)
    run=Path(json.loads((HERE/'latest-run.json').read_text())['run_dir']).resolve()
    assert run.parent==HERE and re.fullmatch(r'run-\d{8}_\d{6}-[0-9a-f]{16}',run.name)
    journal=json.loads((run/'journal.json').read_text());owned=journal['identity']
    assert journal['phase']=='handed_to_operator_manual_console'
    startup.identity(owned['pid'],None,owned['created'])
    artifact=startup.reviewed_artifact();startup.validate_install()
    mount=Path(journal['mount']).resolve()
    assert mount==(startup.GAME/('citadel/citadelcast_walker_'+run.name.rsplit('-',1)[1])).resolve()
    assert journal['dll_sha256']==artifact['dll_sha256']
    assert startup.sha((mount/'bin/win64/server.dll').read_bytes())==artifact['dll_sha256']
    assert all(startup.sha((mount/name).read_bytes())==digest for name,digest in startup.carrier_manifest(artifact).items())
    assert startup.sha(startup.INFO.read_bytes())==startup.STOCK_INFO
    folder=run/(args.label+'-'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'));folder.mkdir(exist_ok=False)
    record={'identity':owned,'dll_sha256':artifact['dll_sha256'],'source_carriers_stock_config_verified':True,
            'agent_commands_or_motion':False,'files':{}}
    for name in ('server.dll.status.json','server.dll.walker-status.json'):
        source=mount/'bin/win64'/name
        if not source.exists():continue
        data=source.read_bytes();value=json.loads(data);assert value['pid']==owned['pid']
        (folder/name).write_bytes(data);record['files'][name]=startup.sha(data)
        if name.endswith('walker-status.json'):
            record['take']={key:value.get(key) for key in ('shot_id','test_mode','phase','result','duration','frames','last_elapsed','follow_sample_present','follow_position_copies','follow_angle_copies','follow_peak_lag','follow_manager_frames','follow_native_frames','follow_gate_checks','follow_max_manager_gap','follow_max_gate_ms','aspect_restore_pending','observer_lease_active','observer_cleanup_unverified','observer_return')}
            record['hero_probe']=value.get('hero_probe')
            record['hero']={key:value.get(key) for key in ('hero_target_handle','hero_target_reason','hero_recenters','hero_root','hero_focus','hero_output_route','hero_entry_fov','hero_primed_before_select','hero_field_updates','hero_phase_costs','hero_read_costs','camera_read_costs','failed_gate_mask','hero_arming_wall_ms','hero_entry_transition')}
            record['hero']['hero_motion_read_cost']=value.get('hero_motion_read_cost')
            record['hero']['hero_native_source']=value.get('hero_native_source')
            trace=value.get('hero_motion_trace')
            if trace:record['motion_trace']={key:trace.get(key) for key in ('format','capacity','count','dropped','rejected','rows_included')}
    record['completed_take_files']=snapshot_takes(mount,owned['pid'],folder)
    if args.screenshot:
        path=args.screenshot.resolve();assert path.parent==Path('C:/Users/Andrew/.t3/userdata/attachments').resolve() and path.suffix=='.png'
        shutil.copyfile(path,folder/'operator-screenshot.png');record['screenshot_sha256']=startup.sha((folder/'operator-screenshot.png').read_bytes())
    startup.write_json(folder/'snapshot.json',record)
    startup.write_json(run/('latest-'+args.label+'.json'),{'snapshot':str(folder)})
    print(json.dumps({'snapshot':str(folder),'take':record.get('take'),'hero_probe':record.get('hero_probe'),'hero':record.get('hero'),'motion_trace':record.get('motion_trace'),'identity':owned}))

if __name__=='__main__':capture()
