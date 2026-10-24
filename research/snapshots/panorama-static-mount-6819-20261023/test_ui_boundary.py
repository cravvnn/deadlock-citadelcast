from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import startup_trial as s
import ui_logs

class UIBoundary(unittest.TestCase):
    def test_ui_search_path_precedes_existing_private_mounts(self):
        original=b'GameInfo\n{\nGame_UILanguage citadel_*LANGUAGE*\nGame "D:/private-chess/assets"\nGame citadel/modlock_dev\nMod "citadel"\nWrite "citadel"\nGame citadel\nGame core\n}\n'
        name='citadelcast_walker_'+'1'*16
        mounted=s.mounted_bytes(original,name)
        self.assertLess(mounted.index(name.encode()),mounted.index(b'D:/private-chess/assets'))
        added=b'Mod\t\tcitadel\nWrite\t\tcitadel\nGame\t\tcitadel/'+name.encode()+b'\n'
        self.assertEqual(mounted.replace(added,b'',1),original)
        self.assertTrue(mounted.index(b'Game_UILanguage')<mounted.index(name.encode()))
    def test_argv_or_file_existence_cannot_pass_actual_filesystem_mount_gate(self):
        mount=Path('B:/game/citadel/citadelcast_walker_'+'2'*16)
        for text in ('[CommandLine] -game '+str(mount),'[Filesystem] GAME "B:/game/citadel/modlock_dev/pak01.vpk"',
                     '[Filesystem] GAME "'+str(mount/'other/pak01.vpk')+'"'):
            with self.subTest(text=text),self.assertRaises(ValueError):ui_logs.verify_mount(text,mount)
        self.assertTrue(ui_logs.verify_mount('[Filesystem] GAME "'+str(mount/'pak01.vpk')+'" (vpk)',mount))
    def test_old_log_mount_is_not_current_session_proof(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);mount=root/'citadelcast_walker_' ;log=root/'console.log'
            old='[Filesystem] GAME "'+str(mount/'pak01.vpk')+'"\n'
            log.write_text(old);before=ui_logs.archive_before(log,root)
            log.write_text(old+'new session without package\n')
            with self.assertRaises(ValueError):ui_logs.require_mount(log,mount,root,before)
            self.assertEqual((root/'prelaunch-console.log').read_text(),old)
    def test_changed_ui_refuses_cleanup_before_any_other_file_is_removed(self):
        with tempfile.TemporaryDirectory() as d:
            game=Path(d);mount=game/'citadel'/('citadelcast_walker_'+'3'*16)
            (mount/'bin/win64').mkdir(parents=True)
            dll=mount/'bin/win64/server.dll';dll.write_bytes(b'native')
            carrier=mount/'walker-shot.kv';carrier.write_bytes(b'camera')
            ui=mount/'pak01_dir.vpk';ui.write_bytes(b'external edit')
            with patch.object(s,'GAME',game),self.assertRaisesRegex(ValueError,'UI package changed'):
                s.cleanup_inactive_mount(mount,s.sha(b'native'),s.sha(b'camera'),None,s.sha(b'reviewed UI'))
            self.assertEqual(dll.read_bytes(),b'native');self.assertEqual(carrier.read_bytes(),b'camera');self.assertTrue(ui.exists())

if __name__=='__main__':unittest.main()
