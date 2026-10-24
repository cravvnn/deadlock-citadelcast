"""Own the mount/rollback/identity boundary; fake process never starts a game."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import startup_trial as trial

class StartupTests(unittest.TestCase):
    def temporary(self):
        folder=tempfile.TemporaryDirectory(dir=trial.HERE)
        assert Path(folder.name).resolve().parent==trial.HERE.resolve()
        return folder

    def test_exact_arguments_flags_no_console_transport(self):
        args=[str(trial.EXE),'-game','citadel','-dev','-insecure','-console','-condebug']
        trial.validate_arguments(args,trial.EXE,None)
        for altered in (args[:3]+args[4:],args[:4]+args[5:],args+['-tools'],args+['-vconsole'],args+['+playdemo','x.dem'],args[:-1],args+['-condebug']):
            with self.assertRaises(ValueError):trial.validate_arguments(altered,trial.EXE,None)
        with self.assertRaises(ValueError):trial.validate_arguments(args,trial.EXE,1234)

    def test_configuration_compare_and_restore(self):
        original=b'GameInfo\r\n{\r\n Game citadel\r\n Game core\r\n}\r\n'
        mounted=trial.mounted_bytes(original,'citadelcast_walker_'+'a'*16)
        self.assertEqual(mounted.count(b'citadelcast_walker_'),1)
        with self.temporary() as folder:
            p=Path(folder)/'gameinfo.gi';p.write_bytes(original)
            trial.replace_exact(p,original,mounted)
            self.assertEqual(trial.restore_exact(p,mounted,original),'restored_exactly')
            self.assertEqual(p.read_bytes(),original)
            p.write_bytes(b'operator edit')
            with self.assertRaises(ValueError):trial.restore_exact(p,mounted,original)
            self.assertEqual(p.read_bytes(),b'operator edit')

    def test_ambiguous_replaced_or_wrong_process_is_rejected(self):
        row={'ProcessId':123,'ExecutablePath':str(trial.EXE),'CreationDate':'first','CommandLine':'not printed'}
        args=[str(trial.EXE),'-game','citadel','-dev','-insecure','-console','-condebug']
        with patch.object(trial,'tokens',return_value=args):
            for rows in ([],[row,row],[{**row,'ProcessId':124}]):
                with patch.object(trial,'process_records',return_value=rows):
                    with self.assertRaises(ValueError):trial.identity(123,None,'first')
            with patch.object(trial,'process_records',return_value=[row]):
                with self.assertRaises(ValueError):trial.identity(123,None,'reused')
                self.assertTrue(trial.identity(123,None,'first')['dev'])

    def test_existing_game_refuses_before_mount_or_process_start(self):
        with patch.object(trial,'validate_install',return_value={}),patch.object(trial,'reviewed_artifact',return_value={}),\
             patch.object(trial,'process_records',return_value=[{'ProcessId':123}]),\
             patch.object(trial,'replace_exact') as replace,patch.object(trial.subprocess,'Popen') as start,\
             patch.object(trial.sys,'argv',['startup_trial.py','--launch-once','--manual-console']):
            with self.assertRaisesRegex(ValueError,'already running'):trial.run()
            replace.assert_not_called();start.assert_not_called()

    def test_mount_rejects_escape_and_duplicate_stock_paths(self):
        for original in (b'Game core\n',b'Game citadel\nGame citadel\n'):
            with self.assertRaises(ValueError):trial.mounted_bytes(original,'citadelcast_walker_'+'b'*16)
        with self.assertRaises(ValueError):trial.mounted_bytes(b'Game citadel\n','../elsewhere')
        for p in (trial.GAME/'citadel',trial.HERE):
            with self.assertRaises(ValueError):trial.cleanup_inactive_mount(p,'unused','unused')

    def fixture(self,here):
        game=here/'game';(game/'citadel').mkdir(parents=True)
        info=game/'citadel/gameinfo.gi';original=b'GameInfo\n{\nGame citadel\nGame core\n}\n';info.write_bytes(original)
        binary=here/'candidate.dll';binary.write_bytes(b'test bytes, never loaded')
        carrier=here/'walker-shot.kv';carrier.write_bytes(b'test camera data')
        artifact={'dll_sha256':trial.sha(binary.read_bytes()),'carrier_sha256':trial.sha(carrier.read_bytes())}
        (here/'ui-test_dir.vpk').write_bytes(b'test UI, never rendered')
        artifact['ui_package_sha256']=trial.sha((here/'ui-test_dir.vpk').read_bytes())
        (here/'candidate-review.json').write_text('{}')
        return game,info,original,binary,carrier,artifact

    def test_failed_start_restores_config_and_removes_only_owned_files(self):
        for conflict in (False,True):
            with self.subTest(conflict=conflict),self.temporary() as directory:
                here=Path(directory);game,info,original,binary,carrier,artifact=self.fixture(here)
                def fail(*args,**kwargs):
                    if conflict:info.write_bytes(b'operator edit')
                    raise OSError('simulated start failure; no process')
                with patch.multiple(trial,HERE=here,GAME=game,INFO=info,DLL=binary,CARRIER=carrier,STOCK_INFO=trial.sha(original)),\
                     patch.object(trial,'validate_install',return_value={'ClientVersion':'6819'}),\
                     patch.object(trial,'reviewed_artifact',return_value=artifact),patch.object(trial,'process_records',return_value=[]),\
                     patch.object(trial,'progress'),patch.object(trial.subprocess,'Popen',side_effect=fail),\
                     patch.object(trial.sys,'argv',['startup_trial.py','--launch-once','--manual-console']):
                    with self.assertRaisesRegex(OSError,'simulated'):trial.run()
                run=Path(json.loads((here/'latest-run.json').read_text())['run_dir'])
                result=json.loads((run/'result.json').read_text())
                self.assertTrue(result['inactive_mount_removed'])
                self.assertEqual(info.read_bytes(),b'operator edit' if conflict else original)
                if conflict:self.assertIn('restoration_error',result)

    def test_success_hands_owned_viewer_to_operator_without_camera_actions(self):
        with self.temporary() as directory:
            here=Path(directory);game,info,original,binary,carrier,artifact=self.fixture(here)
            artifact['carriers']={'walker-shot.kv':artifact['carrier_sha256']}
            for name in ('walker-reverse.kv','bank-sweep.kv','arrival.kv'):
                data=('test camera '+name).encode();(here/name).write_bytes(data)
                artifact['carriers'][name]=trial.sha(data)
            class Process:
                pid=123
                def poll(self):return None
                def terminate(self):raise AssertionError('Do not close a successful viewer')
            def fake_start(arguments,**kwargs):
                self.assertEqual(arguments,[str(trial.EXE),'-game','citadel','-dev','-insecure','-console','-condebug'])
                run=Path(json.loads((here/'latest-run.json').read_text())['run_dir'])
                journal=json.loads((run/'journal.json').read_text());mount=Path(journal['mount'])
                (game/'citadel/console.log').write_text('[Filesystem] GAME "'+str(mount/'pak01.vpk')+'" (vpk)\n')
                (mount/'bin/win64/server.dll.status.json').write_text(json.dumps({'pid':123,'phase':'registered','walker_commands_registered':True}))
                return Process()
            owned={'pid':123,'created':'fixture','port':None,'dev':True,'insecure':True}
            with patch.multiple(trial,HERE=here,GAME=game,INFO=info,DLL=binary,CARRIER=carrier,STOCK_INFO=trial.sha(original)),\
                 patch.object(trial,'validate_install',return_value={'ClientVersion':'6819'}),\
                 patch.object(trial,'reviewed_artifact',return_value=artifact),patch.object(trial,'process_records',return_value=[]),\
                 patch.object(trial,'identity',return_value=owned),patch.object(trial,'progress'),\
                 patch.object(trial.subprocess,'Popen',side_effect=fake_start),\
                 patch.object(trial.sys,'argv',['startup_trial.py','--launch-once','--manual-console']):
                trial.run()
            run=Path(json.loads((here/'latest-run.json').read_text())['run_dir']);result=json.loads((run/'result.json').read_text())
            self.assertEqual(result['phase'],'handed_to_operator_manual_console')
            self.assertFalse(result['automated_camera_started'])
            self.assertFalse(result['watch_broadcast_observed'])
            self.assertEqual(info.read_bytes(),original)
            self.assertEqual((Path(result['mount'])/'walker-shot.kv').read_bytes(),carrier.read_bytes())
            self.assertEqual(result['carriers'],artifact['carriers'])
            for name,digest in artifact['carriers'].items():
                self.assertEqual(trial.sha((Path(result['mount'])/name).read_bytes()),digest)

    def test_manifest_rejects_path_escape_bad_digest_and_original_mismatch(self):
        digest=trial.sha(b'original')
        for values in ({},[],{'../x.kv':digest},{'walker-shot.kv':'f'*64},
                       {'walker-shot.kv':digest,'more.kv':'bad'},
                       {'walker-shot.kv':digest,'C:/x.kv':digest}):
            with self.subTest(values=values),self.assertRaises(ValueError):
                trial.carrier_manifest({'carrier_sha256':digest,'carriers':values})

    def test_changed_secondary_carrier_refuses_review(self):
        with self.temporary() as directory:
            here=Path(directory);game,info,original,binary,carrier,artifact=self.fixture(here)
            (here/'source').mkdir();secondary=here/'arrival.kv';secondary.write_bytes(b'reviewed short path')
            artifact.update(offline_qualified_for_bounded_startup=True,source_manifest={},
                            harness_sha256=trial.sha(Path(trial.__file__).read_bytes()),
                            carriers={'walker-shot.kv':artifact['carrier_sha256'],'arrival.kv':trial.sha(secondary.read_bytes())})
            (here/'candidate-review.json').write_text(json.dumps(artifact))
            with patch.multiple(trial,HERE=here,DLL=binary,CARRIER=carrier):
                trial.reviewed_artifact();secondary.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'camera data changed: arrival.kv'):trial.reviewed_artifact()

    def test_changed_secondary_carrier_retains_all_mount_files(self):
        with self.temporary() as directory:
            here=Path(directory);game=here/'game';mount=game/'citadel'/('citadelcast_walker_'+'e'*16)
            (mount/'bin/win64').mkdir(parents=True)
            dll=mount/'bin/win64/server.dll';dll.write_bytes(b'owned')
            original=mount/'walker-shot.kv';original.write_bytes(b'original')
            secondary=mount/'arrival.kv';secondary.write_bytes(b'operator edit')
            manifest={'walker-shot.kv':trial.sha(b'original'),'arrival.kv':trial.sha(b'reviewed')}
            with patch.object(trial,'GAME',game),self.assertRaisesRegex(ValueError,'camera data changed'):
                trial.cleanup_inactive_mount(mount,trial.sha(b'owned'),manifest['walker-shot.kv'],manifest)
            self.assertEqual(dll.read_bytes(),b'owned');self.assertEqual(original.read_bytes(),b'original')

    def test_unexpected_mount_file_retained_then_exact_multi_cleanup(self):
        with self.temporary() as directory:
            here=Path(directory);game=here/'game';mount=game/'citadel'/('citadelcast_walker_'+'f'*16)
            (mount/'bin/win64').mkdir(parents=True)
            dll=mount/'bin/win64/server.dll';dll.write_bytes(b'owned')
            manifest={}
            for name in ('walker-shot.kv','arrival.kv'):
                (mount/name).write_bytes(name.encode());manifest[name]=trial.sha(name.encode())
            unexpected=mount/'operator-note.txt';unexpected.write_bytes(b'keep')
            with patch.object(trial,'GAME',game):
                with self.assertRaisesRegex(ValueError,'Unexpected'):trial.cleanup_inactive_mount(mount,trial.sha(b'owned'),manifest['walker-shot.kv'],manifest)
                self.assertTrue(dll.exists());self.assertTrue(unexpected.exists())
                unexpected.unlink()
                trial.cleanup_inactive_mount(mount,trial.sha(b'owned'),manifest['walker-shot.kv'],manifest)
                self.assertFalse(mount.exists())

    def test_missing_configuration_is_not_recreated_and_audit_survives(self):
        with self.temporary() as directory:
            here=Path(directory);game,info,original,binary,carrier,artifact=self.fixture(here)
            def fail(*args,**kwargs):
                info.unlink();raise OSError('simulated external configuration removal')
            with patch.multiple(trial,HERE=here,GAME=game,INFO=info,DLL=binary,CARRIER=carrier,STOCK_INFO=trial.sha(original)),\
                 patch.object(trial,'validate_install',return_value={'ClientVersion':'6819'}),\
                 patch.object(trial,'reviewed_artifact',return_value=artifact),patch.object(trial,'process_records',return_value=[]),\
                 patch.object(trial,'progress'),patch.object(trial.subprocess,'Popen',side_effect=fail),\
                 patch.object(trial.sys,'argv',['startup_trial.py','--launch-once','--manual-console']):
                with self.assertRaisesRegex(OSError,'external configuration removal'):trial.run()
            run=Path(json.loads((here/'latest-run.json').read_text())['run_dir']);result=json.loads((run/'result.json').read_text())
            self.assertFalse(info.exists());self.assertIsNone(result['final_gameinfo_sha256'])
            self.assertIn('restoration_error',result)
            self.assertEqual((run/'original.gameinfo.gi').read_bytes(),original)
            self.assertTrue(result['inactive_mount_removed'])

    def test_changed_carrier_prevents_any_cleanup(self):
        with self.temporary() as directory:
            here=Path(directory);game=here/'game';mount=game/'citadel'/('citadelcast_walker_'+'c'*16)
            (mount/'bin/win64').mkdir(parents=True);dll=mount/'bin/win64/server.dll';dll.write_bytes(b'owned')
            (mount/'walker-shot.kv').write_bytes(b'operator edit')
            with patch.object(trial,'GAME',game):
                with self.assertRaisesRegex(ValueError,'camera data changed'):
                    trial.cleanup_inactive_mount(mount,trial.sha(b'owned'),trial.sha(b'original'))
            self.assertEqual(dll.read_bytes(),b'owned')

    def test_changed_artifact_data_source_or_harness_refuses_review(self):
        with self.temporary() as directory:
            here=Path(directory);source=here/'source';source.mkdir();code=source/'part.cpp';code.write_bytes(b'reviewed source')
            dll=here/'server.dll';dll.write_bytes(b'reviewed dll')
            carrier=here/'walker-shot.kv';carrier.write_bytes(b'reviewed camera')
            review={'offline_qualified_for_bounded_startup':True,'harness_sha256':trial.sha(Path(trial.__file__).read_bytes()),
                    'dll_sha256':trial.sha(dll.read_bytes()),'carrier_sha256':trial.sha(carrier.read_bytes()),
                    'source_manifest':{'part.cpp':trial.sha(code.read_bytes())}}
            record=here/'candidate-review.json';record.write_text(json.dumps(review))
            (here/'ui-test_dir.vpk').write_bytes(b'reviewed UI')
            review['ui_package_sha256']=trial.sha((here/'ui-test_dir.vpk').read_bytes())
            record.write_text(json.dumps(review))
            with patch.multiple(trial,HERE=here,DLL=dll,CARRIER=carrier):
                self.assertEqual(trial.reviewed_artifact(),review)
                for path in (dll,carrier,code):
                    before=path.read_bytes();path.write_bytes(b'changed')
                    with self.assertRaises(ValueError):trial.reviewed_artifact()
                    path.write_bytes(before)
                record.write_text(json.dumps({**review,'harness_sha256':'changed'}))
                with self.assertRaisesRegex(ValueError,'harness changed'):trial.reviewed_artifact()

if __name__=='__main__':unittest.main()
