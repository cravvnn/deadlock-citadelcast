import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import take_records as records

class RecordsTests(unittest.TestCase):
    def test_two_completed_records_preserved_before_exact_cleanup(self):
        with tempfile.TemporaryDirectory(dir=records.startup.HERE) as temp:
            game=Path(temp)/'game';mount=game/('citadel/citadelcast_walker_'+'a'*16)
            directory=mount/'bin/win64';directory.mkdir(parents=True)
            archive=Path(temp)/'archive';archive.mkdir()
            for n,profile in enumerate(('turn-with-hero','hold-bearing'),1):
                (directory/f'server.dll.take-{n}.json').write_text(json.dumps({'pid':123,'take_id':n,'phase':0,'hero_profile':profile}))
            with patch.object(records.startup,'GAME',game),patch.object(records.startup,'process_records',return_value=[]):
                hashes=records.snapshot(mount,123,archive);self.assertEqual(len(hashes),2)
                with patch.object(records.startup,'process_records',return_value=[{'pid':123}]):
                    with self.assertRaises(ValueError):records.remove_archived_after_exit(mount,123,archive)
                first=archive/'server.dll.take-1.json';raw=first.read_bytes();first.write_bytes(b'changed')
                with self.assertRaises(ValueError):records.remove_archived_after_exit(mount,123,archive)
                self.assertEqual(len(list(directory.iterdir())),2)
                first.write_bytes(raw)
                self.assertEqual(records.remove_archived_after_exit(mount,123,archive),hashes)
                self.assertEqual(list(directory.iterdir()),[])
    def test_wrong_pid_id_phase_and_escape_refuse(self):
        with tempfile.TemporaryDirectory(dir=records.startup.HERE) as temp:
            game=Path(temp)/'game';mount=game/('citadel/citadelcast_walker_'+'b'*16)
            directory=mount/'bin/win64';directory.mkdir(parents=True)
            path=directory/'server.dll.take-1.json'
            base={'pid':123,'take_id':1,'phase':0,'hero_profile':'turn-with-hero'}
            with patch.object(records.startup,'GAME',game):
                for bad in ({'pid':124},{'take_id':2},{'phase':2},{'hero_profile':'unknown'}):
                    path.write_text(json.dumps({**base,**bad}))
                    with self.assertRaises(ValueError):records.collect(mount,123)
                with self.assertRaises(ValueError):records.collect(game,123)
if __name__=='__main__':unittest.main()
