"""Host-only fault injection for PM's exact four-directory authorization."""
import contextlib
import io
import json
import pathlib
import shlex
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE=pathlib.Path(__file__).resolve().parent
with mock.patch.object(sys,'path',[str(HERE),*sys.path]):
    import dispose_gdb_dirs_20260911 as mod
    import test_single_cleanup as fixture
    import single_request as wire


class DirectoryDispositionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='directory-disposition-tests-')
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        self.source=self.root/'source'
        (self.source/'raw/round_health').mkdir(parents=True)
        (self.source/'raw/round_health/dmesg_before.txt').write_text(fixture.DMESG)
        (self.source/'raw/round_health/zram_before.txt').write_text(fixture.ZRAM)
        self.prior=dict(preflight=dict(boot_id=fixture.BOOT),target_starttime=700)
        (self.source/'execution.json').write_text(json.dumps(self.prior))

    def exercise(self,overrides=None,extra=None,off_failures=0,dirty=False,token=mod.TOKEN,initially_absent=()):
        overrides=overrides or {}
        extra=extra or {}
        state=dict(uid=5001,on=0,off=0,removed=[],events=[])
        args=types.SimpleNamespace(ip='192.0.2.1',output_dir=self.root/('run'+str(len(list(self.root.iterdir())))),pm_authorization=token)
        with mock.patch.object(mod,'known_helpers',return_value={}):
            obj=mod.DirectoryDisposition(args)
        entries={'/usr/share/gdb':['python'],mod.IMAGE:['gdb'],mod.IMAGE+'/gdb':['command','function'],
                 mod.IMAGE+'/gdb/command':[],mod.IMAGE+'/gdb/function':[]}
        entries.update(extra)
        for path in initially_absent:
            parent=str(pathlib.PurePosixPath(path).parent)
            entries[parent].remove(pathlib.PurePosixPath(path).name)
        def git(*a):
            return ('dirty' if dirty else '') if a[0]=='status' else fixture.HEAD
        def transport(label,argv,timeout=20):
            state['events'].append((label,argv))
            if 'shell' not in argv:
                if argv[-2:]==['root','on']:
                    state['uid']=0;state['on']+=1
                if argv[-2:]==['root','off']:
                    state['off']+=1
                    if state['off']>off_failures:
                        state['uid']=5001
                if label in overrides:
                    raise overrides[label]
                return 0,'OK'
            wire.check_body(argv[-1])
            op=shlex.split(argv[-1][len('LC_ALL=C '):-len(wire.SUFFIX)])
            if label in overrides:
                response=overrides[label]
                if callable(response):
                    response=response(entries)
                if isinstance(response,Exception):
                    raise response
                code,payload=response
            elif op==['id']:
                code,payload=0,'uid=%d(owner) gid=5001(owner)'%state['uid']
            elif op[0]=='uname':
                code,payload=0,'rpi4' if op[-1]=='-r' else 'armv7l'
            elif op==['cat','/etc/os-release']:
                code,payload=0,'BUILD_ID='+fixture.single.CONTRACT['identity']['build_id']
            elif op==['rpm','-q','glibc']:
                code,payload=0,'glibc-2.40-1.6.armv7l'
            elif op[0]=='rmdir':
                path=op[-1]
                self.assertTrue((obj.out/'audit.json').is_file())
                saved=json.loads((obj.out/'audit.json').read_text())
                self.assertEqual(saved['directory_dispositions'][-1]['entries_including_hidden'],[])
                self.assertNotIn(path,state['removed'])
                self.assertEqual(entries[path],[])
                state['removed'].append(path)
                entries[str(pathlib.PurePosixPath(path).parent)].remove(pathlib.PurePosixPath(path).name)
                code,payload=0,''
            elif op[0]=='stat':
                path=op[-1]
                if path in state['removed'] or path in initially_absent or path in (mod.WORK,'/opt/usr/glibc_memopt'):
                    code,payload=1,'stat: '+path+': No such file or directory'
                else:
                    code,payload=0,'directory|10|%d|755|0:0|4096|1788932023'%(100+mod.DIRS.index(path))
            elif op[0]=='ls':
                path=op[-1]
                code,payload=(2,'ls: '+path+': No such file or directory') if path in state['removed'] or path in initially_absent else (0,'\n'.join(entries.get(path,[])))
            elif op==mod.PS:
                code,payload=0,fixture.PS_TABLE
            elif op==['dmesg']:
                code,payload=0,fixture.DMESG
            elif op==['cat',mod.BOOT]:
                code,payload=0,fixture.BOOT
            elif op==['cat','/proc/498/stat']:
                code,payload=0,fixture.TARGET_STAT
            elif op==['cat','/sys/block/zram0/mm_stat']:
                code,payload=0,fixture.ZRAM
            elif op==['cat','/proc/meminfo']:
                code,payload=0,'MemTotal: 8117408 kB'
            elif op[0]=='cat' and op[-1].endswith('scaling_governor'):
                code,payload=0,'schedutil'
            elif op[:2]==['rpm','-qa']:
                code,payload=0,'\n'.join(fixture.INVENTORY)
            elif op[:2]==['rpm','-q']:
                code,payload=1,'package %s is not installed'%op[-1]
            elif op[0] in ('df','date'):
                code,payload=0,'fixture'
            else:
                raise AssertionError(op)
            return 77,payload+'\n\nRC=%d\n%s\n'%(code,'DONE' if code==0 else 'FAIL')
        # Gate.run remains real in dispatch hard-limit tests; here only transport is mocked.
        with mock.patch.object(mod,'git',side_effect=git), \
             mock.patch.object(mod,'sources',return_value=(self.prior,[],fixture.INVENTORY)), \
             mock.patch.object(mod,'SOURCE',self.source),mock.patch.object(mod.SingleAudit,'run',side_effect=transport), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            rc=obj.execute()
        return obj,rc,state,output.getvalue()

    def test_bottom_up_three_removed_parent_and_image_preserved_raw_before_mutation(self):
        obj,rc,state,out=self.exercise()
        self.assertEqual(rc,0,out)
        self.assertEqual(state['removed'],list(mod.BOTTOM_UP[:3]))
        self.assertEqual((state['on'],state['off'],state['uid']),(1,1,5001))
        self.assertEqual(obj.receipt['directory_dispositions'][-1]['verdict'],'PRESERVED_IMAGE_ANCESTOR')
        self.assertEqual(obj.receipt['measurement_cells_run'],0)
        self.assertEqual(state['events'][-1][0],'ROOT_ID_OFF_1')
        self.assertEqual(obj.receipt['permission_denied_items'],{})
        self.assertNotEqual(obj.receipt['root_elevation'],'NOT_NEEDED')

    def test_hidden_nonempty_report_only_other_empty_sibling_still_removed(self):
        obj,rc,state,out=self.exercise(extra={mod.BOTTOM_UP[0]:['.keep']})
        self.assertEqual(rc,0,out)
        self.assertEqual(state['removed'],[mod.BOTTOM_UP[1]])
        self.assertEqual(obj.receipt['directory_dispositions'][0]['entries_including_hidden'],['.keep'])
        self.assertEqual(obj.receipt['directory_dispositions'][0]['verdict'],'REPORT_ONLY_PENDING_NONEMPTY')

    def test_symlink_or_inode_change_does_not_delete(self):
        for label,value in (('NONROOT_INITIAL_STAT_0','symbolic link|10|100|755|0:0|20|1'),
                            ('ROOT_RECHECK_0_0','directory|10|999|755|0:0|4096|1')):
            with self.subTest(label=label):
                obj,rc,state,out=self.exercise(overrides={label:(0,value)})
                self.assertEqual(rc,1,out)
                self.assertEqual(state['removed'],[])
                self.assertEqual(state['uid'],5001)

    def test_rmdir_fail_no_retry_and_verify_failure_restore_root(self):
        for label,result in (('ROOT_REMOVE_0',(1,'rmdir: Directory not empty')),
                             ('ROOT_VERIFY_REMOVED_0',(0,'directory|10|100|755|0:0|4096|1'))):
            with self.subTest(label=label):
                obj,rc,state,out=self.exercise(overrides={label:result})
                self.assertEqual(rc,1,out)
                self.assertEqual(state['uid'],5001)
                self.assertEqual(sum(name=='ROOT_REMOVE_0' for name,_ in state['events']),1)
                self.assertFalse(any(name=='ROOT_REMOVE_1' for name,_ in state['events']))

    def test_nonempty_race_is_report_only_without_deletion_retry(self):
        def appear(entries):
            entries[mod.BOTTOM_UP[0]]=['.arrived']
            return 1,'rmdir: '+mod.BOTTOM_UP[0]+': Directory not empty'
        obj,rc,state,out=self.exercise(overrides={'ROOT_REMOVE_0':appear})
        self.assertEqual(rc,0,out)
        self.assertEqual(state['removed'],[mod.BOTTOM_UP[1]])
        self.assertEqual(sum(label=='ROOT_REMOVE_0' for label,_ in state['events']),1)
        self.assertEqual(obj.receipt['directory_dispositions'][0]['entries_including_hidden'],['.arrived'])

    def test_initially_absent_leaf_stays_absent_not_failed_or_removed(self):
        obj,rc,state,out=self.exercise(initially_absent=(mod.BOTTOM_UP[0],))
        self.assertEqual(rc,0,out)
        self.assertEqual(state['removed'],list(mod.BOTTOM_UP[1:3]))
        self.assertEqual(obj.receipt['directory_dispositions'][0]['verdict'],'ALREADY_ABSENT')

    def test_denied_metadata_only_retried_as_root_and_root_on_failure_closes(self):
        label='INITIAL_STAT_%d'%mod.DIRS.index(mod.BOTTOM_UP[0])
        obj,rc,state,out=self.exercise(overrides={'NONROOT_'+label:(1,'stat: fixture: Permission denied')})
        self.assertEqual(rc,0,out)
        self.assertEqual(sum(name=='ROOT_'+label for name,_ in state['events']),1)
        obj,rc,state,out=self.exercise(overrides={'ROOT_ID_ROOT':(0,'uid=5001(owner)')})
        self.assertEqual(rc,1,out)
        self.assertEqual(state['removed'],[])
        self.assertEqual(state['off'],1)

    def test_health_failures_stop_and_root_off_always_attempted(self):
        failures={'ROOT_START_PS':(0,fixture.PS_TABLE.replace('1 0 ? init /sbin/init\n','')),
            'ROOT_START_BOOT':(0,'new-boot'), 'ROOT_END_DMESG':(0,fixture.DMESG+'Out of memory\n'),
            'ROOT_END_GOV_0':(0,'performance'),'ROOT_END_PACKAGES':(0,'added package'),
            'ROOT_END_ZRAM':(0,'1 2 3'),'ROOT_START_TARGET':(1,'Permission denied'),
            'ROOT_START_DMESG':ValueError('missing remote proof')}
        failures.update({'ROOT_END_'+key:(1,'read denied') for key in ('DF_ROOT','DF_OPTUSR','DATE','MEMINFO')})
        for label,result in failures.items():
            with self.subTest(label=label):
                obj,rc,state,out=self.exercise(overrides={label:result})
                self.assertEqual(rc,1,out)
                self.assertEqual((state['off'],state['uid']),(1,5001))

    def test_post_listing_must_agree_with_retained_or_removed_state(self):
        for label,result in (('ROOT_END_LIST_4',(2,'ls: /usr/share/gdb/python: No such file or directory')),
                             ('ROOT_END_LIST_0',(0,''))):
            with self.subTest(label=label):
                obj,rc,state,out=self.exercise(overrides={label:result})
                self.assertEqual(rc,1,out)
                self.assertEqual(state['uid'],5001)

    def test_dirty_snapshot_and_missing_pm_token_never_connect(self):
        for kwargs in ({'dirty':True},{'token':None}):
            obj,rc,state,out=self.exercise(**kwargs)
            self.assertEqual(rc,1,out)
            self.assertEqual(state['events'],[])

    def test_root_off_retry_bounded(self):
        for count,expected in ((1,0),(2,1)):
            obj,rc,state,out=self.exercise(off_failures=count)
            self.assertEqual(rc,expected,out)
            self.assertEqual(state['off'],2)

    def test_transport_logging_fault_after_privilege_switch_still_restores(self):
        for label in ('ROOT_ON','ROOT_OFF_1'):
            with self.subTest(label=label):
                obj,rc,state,out=self.exercise(overrides={label:OSError('host log write failed')})
                self.assertEqual(rc,1,out)
                self.assertEqual(state['uid'],5001)
                self.assertEqual(state['off'],1 if label=='ROOT_ON' else 2)

    def test_foreign_process_not_stopping_or_cleared(self):
        table=fixture.PS_TABLE+'9876 1 pts/4 sh sh -l\n'
        obj,rc,state,out=self.exercise(overrides={'ROOT_START_PS':(0,table),'ROOT_END_PS':(0,table)})
        self.assertEqual(rc,0,out)
        self.assertEqual(obj.receipt['processes_terminated'],0)

    def test_plan_complete_body_200_and_unapproved_delete_local_rejection(self):
        args=types.SimpleNamespace(ip='192.0.2.1',output_dir=self.root/'guard',pm_authorization=mod.TOKEN)
        obj=mod.DirectoryDisposition(args)
        self.assertTrue(all(len(wire.request(op).encode())<=200 for op in obj.allowed.values()))
        obj.phase='ROOT'
        with mock.patch.object(obj,'run') as send:
            for op in (['rmdir','--',mod.IMAGE],['rmdir','--','/tmp'],['rmdir','--',mod.BOTTOM_UP[0]],
                       ['rm','-rf',mod.BOTTOM_UP[0]],['kill','-TERM','--','12345'],['cat','/etc/shadow']):
                with self.subTest(op=op),self.assertRaises(ValueError):
                    obj.op('BAD',op,False)
            send.assert_not_called()

    def test_attributed_helper_is_archived_without_termination_authority(self):
        args=types.SimpleNamespace(ip='192.0.2.1',output_dir=self.root/'helper',pm_authorization=mod.TOKEN)
        obj=mod.DirectoryDisposition(args)
        obj.phase='ROOT'
        obj.receipt['root_authorization']={'id_after_on':'uid=0(root)'}
        obj.helpers={12345:dict(starttime=700,exe=('/bin/sh',),script='run_cell_remote.sh')}
        table=fixture.PS_TABLE+'12345 1 ? sh /bin/sh '+mod.WORK+'/run_cell_remote.sh\n'
        import base64
        cmd=base64.b64encode(('/bin/sh\0'+mod.WORK+'/run_cell_remote.sh\0').encode()).decode()
        stat=fixture.TARGET_STAT.replace('498 (enlightenment)','12345 (sh)')
        with mock.patch.object(obj,'proc_read',side_effect=[stat,'/bin/sh',cmd]),mock.patch.object(obj,'run') as send:
            with self.assertRaisesRegex(ValueError,'cannot terminate'):
                obj.inspect_processes('START_PS',table)
            send.assert_not_called()
        self.assertEqual(json.loads((obj.out/'audit.json').read_text())['process_observations']['START_PS'][0]['verdict'],
            'STOP_PROJECT_HELPER_ARCHIVED_NOT_CLEARED_THIS_ROUND')
        with mock.patch.object(mod.SingleAudit.__bases__[0],'run') as send:
            with self.assertRaisesRegex(ValueError,'NOT SENT'):
                obj.run('TOO_LONG',['sdb','shell','x'*201])
            send.assert_not_called()


if __name__=='__main__':
    unittest.main()
