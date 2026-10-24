"""Verify exported source hashes and run offline research owners; never launches a game."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / 'research/snapshots'

def run(args, cwd=ROOT):
    print('+ ' + ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true', help='also build and run MSVC/Windows offline fixtures')
    args = parser.parse_args()
    started = time.perf_counter()
    manifest = json.loads((ROOT / 'research/SNAPSHOT_MANIFEST.json').read_text())
    for relative, expected in manifest['copied_files'].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(SNAPSHOTS.resolve()):
            raise ValueError('Snapshot manifest escaped the source archive')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Reviewed snapshot changed: ' + relative)
    print(f"Exact exported source/fixture hashes: {len(manifest['copied_files'])}", flush=True)
    py = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', '.', '-q']
    for name in ('camera-condebug-6819-20261023', 'panorama-static-mount-6819-20261023'):
        run(py, SNAPSHOTS / name)
    run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*obstruction.py', '-q'],
        SNAPSHOTS / 'overnight-camera-lab-20261023')
    run(['node', '--test', 'tests/test_recap.js'], SNAPSHOTS / 'panorama-broadcast-6819-20261023')
    run(['node', '--test', 'test_static_probe.js'], SNAPSHOTS / 'panorama-static-watch-6819-20261023')
    if args.native:
        build = ROOT / 'build/research-offline'
        run(['cmake', '-S', ROOT / 'research/offline-native', '-B', build, '-A', 'x64'])
        run(['cmake', '--build', build, '--config', 'Release', '--parallel', '4'])
        run(['ctest', '--test-dir', build, '-C', 'Release', '--output-on-failure'])
    print(f'Offline research verification: {time.perf_counter() - started:.3f}s; no live compatibility claim.')

if __name__ == '__main__':
    main()
