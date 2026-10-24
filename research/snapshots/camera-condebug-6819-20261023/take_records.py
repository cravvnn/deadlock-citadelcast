"""Bounded read-only take snapshots; removal is separate and requires no game."""
from pathlib import Path
import json,re
import startup_trial as startup

def collect(mount,pid):
    mount=Path(mount).resolve();parent=(startup.GAME/'citadel').resolve()
    if mount.parent!=parent or not re.fullmatch(r'citadelcast_walker_[0-9a-f]{16}',mount.name):
        raise ValueError('Not an owned mount')
    directory=mount/'bin/win64'
    if directory.resolve()!=directory:raise ValueError('Redirected status directory')
    records={}
    for path in directory.glob('server.dll.take-*.json'):
        match=re.fullmatch(r'server\.dll\.take-([1-9][0-9]{0,19})\.json',path.name)
        if not match or path.is_symlink() or path.resolve()!=path or path.stat().st_size>16*1024*1024:
            raise ValueError('Unexpected take record')
        raw=path.read_bytes();value=json.loads(raw)
        if path.read_bytes()!=raw:raise ValueError('Take record still being written')
        if value.get('pid')!=pid or value.get('take_id')!=int(match[1]) or value.get('phase')!=0:
            raise ValueError('Take record identity or completion differs')
        if value.get('hero_profile') not in ('turn-with-hero','hold-bearing','legacy-native-bearing'):
            raise ValueError('Unknown take profile')
        records[path.name]=raw
    return records

def snapshot(mount,pid,destination):
    records=collect(mount,pid);destination=Path(destination)
    hashes={}
    for name,raw in records.items():
        with (destination/name).open('xb') as out:out.write(raw)
        hashes[name]=startup.sha(raw)
    return hashes

def remove_archived_after_exit(mount,pid,destination):
    # Call only during an independently audited owned-process close. The normal
    # startup cleanup continues to refuse unknown files until these are saved.
    if startup.process_records():raise ValueError('Game still running; retaining take records')
    records=collect(mount,pid);destination=Path(destination)
    for name,raw in records.items():
        if (destination/name).read_bytes()!=raw:raise ValueError('Archive differs; retaining all records')
    if startup.process_records():raise ValueError('Game appeared; retaining take records')
    for name,raw in records.items():
        target=Path(mount).resolve()/'bin/win64'/name
        if target.resolve()!=target or target.read_bytes()!=raw:raise ValueError('Take changed; retaining remaining records')
        target.unlink()
    return {name:startup.sha(raw) for name,raw in records.items()}
