#!/usr/bin/env python3
"""PM 2026-09-11 exact empty-directory disposition; never run measurements.

Only three leaf/inner directories are expected to be removable. The image's
python directory and its necessary parent are retained. Nonempty = REPORT_ONLY.
Every remote operation, including proof framing, is locally bounded to 200 B.
"""
import argparse
import base64
import hashlib
import json
import pathlib
import re

from audit_single_cleanup_20260911 import (SingleAudit, sources, ROOT, SOURCE,
    PS, CRASH, BOOT, WORK, GDB_NAMES, ANALYSIS, health_delta, git, utc, request,
    parse, absent, absent_listing)
from audit_restricted_resume_20260911 import RestrictedResume, known_helpers, process_rows

TOKEN = 'PM-GDB-DIRECTORIES-20260911'
IMAGE = '/usr/share/gdb/python'
BOTTOM_UP = (IMAGE+'/gdb/function', IMAGE+'/gdb/command', IMAGE+'/gdb', '/usr/share/gdb')
ANCESTORS = ('/usr', '/usr/share', '/usr/share/gdb', IMAGE, IMAGE+'/gdb')
DIRS = tuple(dict.fromkeys((*ANCESTORS, *BOTTOM_UP)))
FORMAT = '%F|%d|%i|%a|%u:%g|%s|%Y'


def stat(path):
    return ['stat', '-c', FORMAT, '--', path]


def directory_identity(text):
    fields = text.split('|')
    if (len(fields) != 7 or fields[0] != 'directory' or
            not all(re.fullmatch(r'\d+', fields[i]) for i in (1,2,3,5,6)) or
            not re.fullmatch(r'\d+:\d+', fields[4])):
        raise ValueError('not a real directory; symlinks are never followed for deletion')
    # mtime/size can legitimately change as authorized children are removed.
    return tuple(fields[:5])


class DirectoryDisposition(SingleAudit):
    authorization_token = TOKEN
    proc_read = RestrictedResume.proc_read

    def __init__(self, args):
        super().__init__(args)
        self.helpers = known_helpers()
        self.process_ops, self.signals, self.inspected = set(), set(), set()
        self.directory_proofs = {}
        self.removal_ready = set()
        self.allowed = {}
        self.receipt.update(schema='system-before-after.directory-disposition.v1',
            pm_decision_date='2026-09-11', directories_removed=[], directory_dispositions=[],
            preserved_image_directory=IMAGE, accepted_measurements='21 PRESERVED',
            foreign_process_policy='REPORT_ONLY; do not stop or clear foreign processes')
        for prefix in ('START', 'END'):
            self.allowed.update(self.snapshot_plan(prefix))
        for i, path in enumerate(DIRS):
            self.allowed['INITIAL_STAT_%d'%i] = stat(path)
        for i, path in enumerate((*BOTTOM_UP, IMAGE)):
            self.allowed['INITIAL_LIST_%d'%i] = ['ls','-A','--',path]
            self.allowed['END_DIR_%d'%i] = stat(path)
            self.allowed['END_LIST_%d'%i] = ['ls','-A','--',path]
        for i, path in enumerate(BOTTOM_UP):
            self.allowed['CHECK_LIST_%d'%i] = ['ls','-A','--',path]
            self.allowed['NONEMPTY_RACE_%d'%i] = ['ls','-A','--',path]
            self.allowed['VERIFY_REMOVED_%d'%i] = stat(path)
            for j, ancestor in enumerate(DIRS):
                if path == ancestor or path.startswith(ancestor+'/'):
                    self.allowed['RECHECK_%d_%d'%(i,j)] = stat(ancestor)
        for argv in self.allowed.values():
            request(argv)
        for path in BOTTOM_UP:
            request(['rmdir','--',path])

    @staticmethod
    def snapshot_plan(prefix):
        ops = {'BOOT': ['cat',BOOT], 'PS': PS, 'DMESG': ['dmesg'],
            'ZRAM': ['cat','/sys/block/zram0/mm_stat'],
            'ALERTS': ['ls','-A','--',CRASH], 'TARGET': ['cat','/proc/498/stat'],
            'PACKAGES': ['rpm','-qa','--queryformat','%{NAME} %{VERSION}-%{RELEASE}.%{ARCH}\\n'],
            'DF_ROOT': ['df','-k','/'], 'DF_OPTUSR': ['df','-k','/opt/usr'],
            'WORK': stat(WORK), 'WORK_PARENT': stat('/opt/usr/glibc_memopt'),
            'DATE': ['date','-u'], 'MEMINFO': ['cat','/proc/meminfo'],
            'TOP_TMP': ['ls','-A','--','/tmp'], 'TOP_HOME': ['ls','-A','--','/home'],
            'TOP_OPTUSR': ['ls','-A','--','/opt/usr']}
        ops.update({'GOV_%d'%i:['cat','/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor'%i] for i in range(4)})
        ops.update({'ABSENT_'+n:['rpm','-q',n] for n in GDB_NAMES})
        return {prefix+'_'+key: value for key,value in ops.items()}

    def allow_scoped_root(self, scope, argv):
        if scope in ('START_PS','END_PS') and tuple(argv) in self.process_ops:
            return True
        return super().allow_scoped_root(scope,argv)

    def run(self,label,argv,timeout=20):
        try:
            return super().run(label,argv,timeout)
        except OSError as error:
            self.receipt['recording_error']=str(error)
            raise

    def op(self, label, argv, defer=True, scope=None):
        if argv[0] in ('rm','kill'):
            raise ValueError('this root round permits rmdir only; file/process mutation not authorized')
        if argv[0] == 'rmdir':
            path = argv[-1]
            if (self.phase != 'ROOT' or argv != ['rmdir','--',path] or
                    path not in BOTTOM_UP or path not in self.removal_ready or
                    label != 'REMOVE_%d'%BOTTOM_UP.index(path)):
                raise ValueError('rmdir requires exact PM scope and archived empty-directory proof')
            self.removal_ready.remove(path)  # one dispatch only, including failures
            _, text = self.run('ROOT_'+label,['sdb','-s',self.serial,'shell',request(argv)])
            result = parse(text)
            self.results[label] = result
            return result
        if self.phase == 'ROOT' and label in self.allowed:
            if argv != self.allowed[label]:
                raise ValueError('root operation differs from frozen disposition list')
            self.pending[label] = dict(argv=argv,directory=argv[-1] if argv[0]=='ls' else None)
        return super().op(label,argv,defer,scope)

    def inspect_processes(self,label,text):
        if self.phase!='ROOT' or not self.receipt['root_authorization']['id_after_on'].startswith('uid=0('):
            raise ValueError('full-system view requires authorized root context')
        rows,collectors=process_rows(text)
        if 498 not in rows or rows[498]['comm']!='enlightenment':
            raise ValueError('original daemon missing from full-system view')
        observations=[]
        for pid,row in rows.items():
            if pid in collectors or pid==498:
                continue
            candidate=pid in self.helpers or re.search(r'alloc_bench|gst_loop_decode|gst-launch|^gdb$|sample_smaps|run_cell_remote',row['comm']) or WORK+'/' in row['args']
            if not candidate and row['tty']=='?':
                continue
            record=dict(pid=pid,**row,verdict='REPORT_ONLY_NONPROJECT_OR_UNATTRIBUTED_NOT_CLEARED')
            observations.append(record)
            self.receipt.setdefault('process_observations',{})[label]=observations
            self.save()
            if pid not in self.helpers:
                continue
            expected=self.helpers[pid]
            current=self.proc_read(label,pid,'STAT',['cat','/proc/%d/stat'%pid])
            identity=ANALYSIS.proc_stat(current)
            if identity['pid']!=pid or identity['starttime']!=expected['starttime']:
                continue
            exe=self.proc_read(label,pid,'EXE',['readlink','/proc/%d/exe'%pid])
            command=self.proc_read(label,pid,'CMDLINE',['base64','/proc/%d/cmdline'%pid])
            argv=base64.b64decode(''.join(command.splitlines()),validate=True).decode().split('\0')
            if exe.removesuffix(' (deleted)') in expected['exe'] and WORK+'/'+expected['script'] in argv:
                record['verdict']='STOP_PROJECT_HELPER_ARCHIVED_NOT_CLEARED_THIS_ROUND'
                self.save()
                raise ValueError('attributed project helper still present; this root round cannot terminate it')
        self.receipt.setdefault('process_views',{})[label]=dict(rows=len(rows),pid_1=True,
            target_498=True,context='UID=0; ps -e all-system selection',foreign_is_report_only=True)
        self.save()

    def directories_before(self):
        for i,path in enumerate(DIRS):
            result = self.op('INITIAL_STAT_%d'%i,stat(path))
            if result is None:
                continue
            if absent(*result) and path in BOTTOM_UP:
                self.directory_proofs[path] = None
            elif result[0]:
                raise ValueError('directory metadata failed: '+path)
            else:
                self.directory_proofs[path] = directory_identity(result[1])
        for i,path in enumerate((*BOTTOM_UP,IMAGE)):
            result = self.op('INITIAL_LIST_%d'%i,['ls','-A','--',path])
            if result is not None and result[0] and not absent_listing(*result):
                raise ValueError('directory listing failed: '+path)
        self.receipt['directory_identity_before'] = self.directory_proofs
        self.save()

    def dispose(self):
        for i,path in enumerate(BOTTOM_UP):
            record = dict(path=path,verdict='NOT_EVALUATED')
            self.receipt['directory_dispositions'].append(record)
            if self.directory_proofs[path] is None:
                record['verdict'] = 'ALREADY_ABSENT'
                continue
            # Check each ancestor and leaf without following a symlink. Kernel
            # rmdir is nonrecursive and refuses nonempty dirs if a child appears.
            for j,ancestor in enumerate(DIRS):
                if path == ancestor or path.startswith(ancestor+'/'):
                    text = self.ok('RECHECK_%d_%d'%(i,j),stat(ancestor),False)
                    if directory_identity(text) != self.directory_proofs[ancestor]:
                        raise ValueError('directory identity changed; no deletion: '+ancestor)
            entries = self.ok('CHECK_LIST_%d'%i,['ls','-A','--',path],False)
            record['entries_including_hidden'] = entries.splitlines()
            if entries:
                record['verdict'] = ('PRESERVED_IMAGE_ANCESTOR' if path=='/usr/share/gdb' and
                    entries=='python' else 'REPORT_ONLY_PENDING_NONEMPTY')
                self.save()
                continue
            record['empty_proof_utc'] = utc()
            self.save()  # all metadata and empty listing on host before rmdir
            self.removal_ready.add(path)
            result = self.op('REMOVE_%d'%i,['rmdir','--',path],False)
            if result[0]:
                if result[1].endswith(': Directory not empty'):
                    entries=self.ok('NONEMPTY_RACE_%d'%i,['ls','-A','--',path],False)
                    if entries:
                        record.update(verdict='REPORT_ONLY_PENDING_NONEMPTY',entries_including_hidden=entries.splitlines(),
                            reason='became nonempty before rmdir; kernel refused; no deletion retry')
                        self.save()
                        continue
                raise ValueError('rmdir failed; no retry: '+path+': '+result[1])
            if not absent(*self.op('VERIFY_REMOVED_%d'%i,stat(path),False)):
                raise ValueError('directory removal not verified: '+path)
            record['verdict'] = 'ARCHIVED_RMDIR_VERIFIED_ABSENT'
            self.receipt['directories_removed'].append(path)
            self.save()

    def health(self,prefix,prior,inventory):
        for label,argv in self.snapshot_plan(prefix).items():
            self.op(label,argv,False)
        def good(name):
            rc,text = self.results[prefix+'_'+name]
            if rc:
                raise ValueError('health read failed: '+prefix+'_'+name)
            return text
        if good('BOOT') != prior['preflight']['boot_id']:
            raise ValueError('boot changed since accepted G4; no measurements rerun')
        self.receipt['boot_id'] = good('BOOT')
        self.inspect_processes(prefix+'_PS',good('PS'))
        target = ANALYSIS.proc_stat(good('TARGET'))
        if target['pid'] != 498 or target['starttime'] != prior['target_starttime']:
            raise ValueError('original daemon restarted')
        increment = health_delta((SOURCE/'raw/round_health/dmesg_before.txt').read_text(),good('DMESG'),
            (SOURCE/'raw/round_health/zram_before.txt').read_text(),good('ZRAM'))
        (self.out/('dmesg_increment_'+prefix+'.txt')).write_text('\n'.join(increment)+'\n')
        for n in range(4):
            if good('GOV_%d'%n) != 'schedutil':
                raise ValueError('governor not restored')
        for name in ('DF_ROOT','DF_OPTUSR','DATE','MEMINFO'):
            if not good(name):
                raise ValueError('empty health observation: '+prefix+'_'+name)
        memory=re.search(r'^MemTotal:\s+(\d+) kB$',good('MEMINFO'),re.M)
        if not memory or not 8036234 <= int(memory[1]) <= 8198582:
            raise ValueError('MemTotal drift in cleanup snapshot')
        actual = sorted(good('PACKAGES').splitlines())
        self.receipt['package_inventory_'+prefix] = dict(before_count=len(inventory),current_count=len(actual),
            added=sorted(set(actual)-set(inventory)),removed=sorted(set(inventory)-set(actual)))
        if actual != inventory:
            raise ValueError('package inventory changed')
        for name in GDB_NAMES:
            if self.results[prefix+'_ABSENT_'+name] != (1,'package %s is not installed'%name):
                raise ValueError('package still present: '+name)
        for name in ('WORK','WORK_PARENT'):
            if not absent(*self.results[prefix+'_'+name]):
                raise ValueError('work directory residue; archive/disposition needed')
        for name in ('TOP_TMP','TOP_HOME','TOP_OPTUSR'):
            entries=good(name).splitlines()
            suspects=[x for x in entries if re.search(r'alloc_bench|gst_loop_decode|glibc_memopt|small_320x240|sample_smaps|run_cell_remote',x)]
            if suspects:
                self.receipt['top_level_suspects']=suspects
                raise ValueError('new project file candidate; requires exact archived disposition')
        code,listing = self.results[prefix+'_ALERTS']
        if code and not absent_listing(code,listing):
            raise ValueError('stability directory unreadable')
        names=listing.splitlines() if not code else []
        self.receipt['stability_'+prefix]=dict(count=len(names),entries=names)
        if names:
            self.archive_alerts(prefix+'_ALERTS',names)
            self.classify_alerts(prefix+'_ALERTS',names,prior)
        self.receipt['health_'+prefix]=dict(oom_lmk_new=0,zram_three_delta=[0,0,0],
            attributable_alerts_new=0,boot_unchanged=True,dmesg_prefix_retained=True,dmesg_increment_lines=len(increment))
        self.save()

    def execute(self):
        try:
            commit=git('rev-parse','HEAD')
            if git('status','--porcelain') or git('ls-remote','origin','refs/heads/main').split()[0]!=commit:
                raise ValueError('clean committed and pushed main required before board connection')
            self.receipt['executor_commit']=commit
            prior,_,inventory=sources()
            self.receipt['source_execution_sha256']=hashlib.sha256((SOURCE/'execution.json').read_bytes()).hexdigest()
            if self.args.pm_authorization != TOKEN:
                raise ValueError('exact PM directory authorization required')
            self.run('SDB_VERSION',['sdb','version'])
            _,text=self.run('CONNECT',['sdb','connect',self.addr])
            if re.search(r'failed|unable|cannot|error|HOST_TIMEOUT',text,re.I):
                raise ValueError('connection failed; no retry')
            self.identity()
            self.directories_before()
            self.receipt['nonroot_sweep_completed_utc']=utc()
            # Do not alias the dynamic root authorization register into the
            # historical list of actual non-root permission failures.
            self.receipt['permission_denied_items']=json.loads(json.dumps(self.pending))
            # The prior root ps proof establishes nonroot visibility is incomplete;
            # deletion of UID=0 system dirs also needs this explicit one-round grant.
            self.receipt['root_authorization']=dict(approved_by='PM',decision_date='2026-09-11',
                scope='four-directory disposition and listed post-disposition health checks only',
                id_before=self.ok('ID_BEFORE_ROOT',['id'],False),root_off='NOT-EVALUATED')
            self.receipt['root_elevation']='PM_EXACT_DIRECTORY_DISPOSITION_AND_CLEANUP_CHECKS'
            if not self.receipt['root_authorization']['id_before'].startswith('uid=5001('):
                raise ValueError('UID changed before root')
            (self.out/'root_scope.json').write_text(json.dumps(dict(reads=self.allowed,
                removable_directories=BOTTOM_UP,preserved_directory=IMAGE),indent=2)+'\n')
            self.save()
            self.raised=True
            self.run('ROOT_ON',['sdb','-s',self.serial,'root','on'])
            self.phase='ROOT'
            self.receipt['root_authorization']['id_after_on']=self.ok('ID_ROOT',['id'],False)
            if not self.receipt['root_authorization']['id_after_on'].startswith('uid=0('):
                raise ValueError('root not established')
            # Retry ONLY earlier permission-denied metadata, not successful reads.
            for label,item in list(self.pending.items()):
                result=self.op(label,item['argv'],False)
                if result[0]:
                    raise ValueError('directory remains unreadable as root')
                if label.startswith('INITIAL_STAT_'):
                    self.directory_proofs[DIRS[int(label.rsplit('_',1)[1])]]=directory_identity(result[1])
            self.health('START',prior,inventory)
            self.dispose()
            for i,path in enumerate((*BOTTOM_UP,IMAGE)):
                result=self.op('END_DIR_%d'%i,stat(path),False)
                if path in self.receipt['directories_removed'] or self.directory_proofs[path] is None:
                    if not absent(*result):
                        raise ValueError('removed directory reappeared')
                elif result[0] or directory_identity(result[1])!=self.directory_proofs[path]:
                    raise ValueError('retained directory identity not preserved')
                listing=self.op('END_LIST_%d'%i,['ls','-A','--',path],False)
                removed=path in self.receipt['directories_removed'] or self.directory_proofs[path] is None
                if (removed and not absent_listing(*listing)) or (not removed and listing[0]):
                    raise ValueError('post-disposition listing disagrees with disposition state')
            self.health('END',prior,inventory)
            self.receipt['verdict']='PASS_READONLY_CLEANUP'
            self.receipt['scope']='delayed cleanup only; directory rmdir exceptions explicitly recorded; no measurements'
        except Exception as error:
            self.receipt.update(verdict='STOP',reason=str(error).replace(self.addr,'<TEST_BOARD_IP>'))
        finally:
            if self.raised:
                self.drop_root()
            elif 'id_before' in self.receipt:
                try:
                    self.receipt['id_final']=self.ok('ID_FINAL',['id'],False)
                except Exception as error:
                    self.receipt['final_id_error']=str(error)
            if self.receipt.get('recording_error'):
                self.receipt.update(verdict='STOP',reason='command recording/transport error; see recording_error')
            self.receipt['end_utc']=utc()
            self.save()
        print('FINAL_DIRECTORY_DISPOSITION',json.dumps(self.receipt),flush=True)
        return 0 if self.receipt['verdict']=='PASS_READONLY_CLEANUP' else 1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ip',required=True)
    p.add_argument('--output-dir',required=True,type=pathlib.Path)
    p.add_argument('--pm-authorization',required=True,choices=[TOKEN])
    args=p.parse_args()
    if not args.output_dir.resolve().is_relative_to(ROOT/'board_results'):
        p.error('output must be new local board_results directory')
    return DirectoryDisposition(args).execute()


if __name__=='__main__':
    raise SystemExit(main())
