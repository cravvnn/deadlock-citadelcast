"""Read-only VPK directory inventory and bounded resource extraction into this lab."""
from pathlib import Path
import struct, json, hashlib
from functools import lru_cache

LAB = Path(__file__).resolve().parent
PAK = Path('B:/SteamLibrary/steamapps/common/Deadlock/game/citadel/pak01_dir.vpk')

@lru_cache(maxsize=1)
def entries():
    raw = PAK.read_bytes()
    signature, version, tree_size = struct.unpack_from('<III', raw)
    assert signature == 0x55aa1234 and version == 2
    pos = 28
    def string():
        nonlocal pos
        end = raw.index(0, pos)
        value = raw[pos:end].decode('utf-8')
        pos = end + 1
        return value
    out = {}
    while ext := string():
        while folder := string():
            while name := string():
                crc, preload, archive, offset, length, terminator = struct.unpack_from('<IHHIIH', raw, pos)
                assert terminator == 0xffff
                pos += 18
                prefix = raw[pos:pos+preload]
                pos += preload
                key = ('' if folder == ' ' else folder + '/') + name + '.' + ext
                out[key] = (archive, offset, length, prefix)
    return out, 28 + tree_size

def read(key):
    index, data_offset = entries()
    archive, offset, length, prefix = index[key]
    assert length < 4_000_000
    source = PAK if archive == 0x7fff else PAK.with_name(f'pak01_{archive:03}.vpk')
    with source.open('rb') as f:
        f.seek(offset + (data_offset if archive == 0x7fff else 0))
        return prefix + f.read(length)

def blocks(raw):
    size, header, version, relative, count = struct.unpack_from('<IHHII', raw)
    assert header == 12 and count < 128
    result = {}
    for n in range(count):
        pos = 8 + relative + 12*n
        kind, offset, length = struct.unpack_from('<4sII', raw, pos)
        result[kind.decode()] = raw[pos+4+offset:pos+4+offset+length]
    return result

def panorama_text(raw):
    # Panorama image-table format corroborated against ValveResourceFormat/Panorama.cs.
    data = blocks(raw)['DATA']
    count = struct.unpack_from('<H', data, 4)[0]
    version = struct.unpack_from('<H', raw, 6)[0]
    pos = 6
    for _ in range(count):
        pos = data.index(0, pos) + 1 + (8 if version >= 3 else 4)
    return data[pos:].decode('utf-8').rstrip('\0')

if __name__ == '__main__':
    index, _ = entries()
    paths = [k for k in index if k.startswith('panorama/') and any(s in k.lower() for s in ('spectat', 'hud', 'styles', 'kill', 'soul'))]
    (LAB/'native-inventory.json').write_text(json.dumps({'pak':str(PAK), 'pak_sha256':hashlib.sha256(PAK.read_bytes()).hexdigest(), 'paths':paths},indent=2))
    for key in paths:
        if key.endswith(('.vxml_c','.vcss_c','.vjs_c')) and any(s in key.lower() for s in ('spectat','styles/citadel','styles/hud')):
            raw = read(key)
            data = blocks(raw).get('DATA',b'')
            out = LAB/'native-evidence'/key
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_bytes(data)
    print(json.dumps({'indexed':len(index),'matching_paths':len(paths),'extracted':len(list((LAB/'native-evidence').rglob('*_c')))}))
