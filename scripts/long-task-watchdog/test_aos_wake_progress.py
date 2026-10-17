import tempfile
import unittest
from pathlib import Path
from subprocess import run
from aos_wake_progress import observe, snapshot, checkpoint_snapshot, exact_file, recovery_guidance, process_identity, command_observation, THREAD
import json
import os
from datetime import datetime, timezone, timedelta

class ProgressTest(unittest.TestCase):
    def snap(self, commit='a', at=100):
        return dict(repo='/repo', thread='thread', branch='m1', head=commit, code_commit=commit, code_time=at)

    def test_two_unchanged_wakes_require_review(self):
        a=observe({},self.snap(),'001',110)
        b=observe(a,self.snap(),'002',120)
        c=observe(b,self.snap(),'003',130)
        self.assertEqual(c['action'],'REVIEW_REQUIRED')
        self.assertEqual(c['unchanged_wakes'],2)

    def test_duplicate_or_old_event_does_not_increment(self):
        a=observe({},self.snap(),'002',110)
        self.assertEqual(observe(a,self.snap(),'002',900),a)
        self.assertEqual(observe(a,self.snap(),'001',900),a)

    def test_code_change_resets_counter(self):
        a=observe({},self.snap(),'001',2000)
        self.assertEqual(a['action'],'REVIEW_REQUIRED')
        b=observe(a,self.snap('b',2010),'002',2020)
        self.assertEqual(b['action'],'CONTINUE')
        self.assertEqual(b['unchanged_wakes'],0)

    def test_wrong_thread_or_repo_rejected(self):
        a=observe({},self.snap(),'001',110)
        for field in ('thread','repo'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                observe(a,dict(self.snap(),**{field:'other'}),'002',120)

    def test_wrong_branch_rejected(self):
        with self.assertRaises(ValueError):
            observe({},dict(self.snap(),branch='other'),'001',110)

    def test_document_commit_is_not_code_progress(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*args):
                return run(['git','-C',d,*args],check=True,capture_output=True,text=True).stdout.strip()
            git('init','-b','m1');git('config','user.name','test');git('config','user.email','test@invalid')
            p=Path(d)/'services';p.mkdir();(p/'feature.py').write_text('x=1\n')
            git('add','services/feature.py');git('commit','-m','code')
            original=snapshot(Path(d),'thread')['code_commit']
            (p/'notes.md').write_text('notes')
            git('add','services/notes.md');git('commit','-m','docs')
            s=snapshot(Path(d),'thread')
            self.assertEqual(s['code_commit'],original)
            self.assertNotEqual(s['head'],original)

class AttributedProgressTest(unittest.TestCase):
    def attributed(self, fingerprint='one', task='task'):
        return dict(repo='/repo',thread='thread',branch='m1',head='a',code_commit='a',code_time=100,
                    checkpoint=dict(task_id=task,owner='owner',authority_revision='AOS-001329',
                                    step='RED',fingerprint=fingerprint))

    def test_task_file_change_is_reviewable_progress_despite_old_code(self):
        a=observe({},self.attributed(),'001',3000)
        b=observe(a,self.attributed('two'),'002',3010)
        self.assertEqual(b['action'],'TASK_PROGRESS_OBSERVED')
        self.assertEqual(b['unchanged_wakes'],0)

    def test_other_commit_does_not_clear_task_stall(self):
        a=observe({},self.attributed(),'001',3000)
        current=self.attributed();current.update(code_commit='other',code_time=3010)
        b=observe(a,current,'002',3020)
        self.assertEqual(b['action'],'REVIEW_REQUIRED')

    def test_task_switch_does_not_count_as_progress(self):
        a=observe({},self.attributed(),'001',3000)
        b=observe(a,self.attributed('two','different'),'002',3010)
        self.assertEqual(b['action'],'REVIEW_REQUIRED')

    def test_duplicate_file_change_does_not_refresh_state(self):
        a=observe({},self.attributed(),'002',3000)
        self.assertEqual(observe(a,self.attributed('two'),'002',3010),a)

class CheckpointSafetyTest(unittest.TestCase):
    def setup_context(self, root):
        repo=root/'repo';repo.mkdir();task='task'
        (repo/'scripts').mkdir();(repo/'scripts/a.py').write_text('value=1')
        evidence=repo/'.evidence'/task;evidence.mkdir(parents=True)
        context=root/'context';m=context/'memory';(m/'receipts/tasks').mkdir(parents=True)
        receipt={'task_id':task,'owner':'owner','base_revision':'AOS-001329','status':'ACTIVE',
                 'lease_expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                 'scope':['aos-platform/scripts'],'excluded_scope':[]}
        (m/'authority.json').write_text(json.dumps({'project_revision':'AOS-001329'}))
        (m/'leases.json').write_text(json.dumps({'leases':[receipt]}))
        (m/'receipts/tasks/task.json').write_text(json.dumps(receipt))
        cp={'schema':'aos-engineering-checkpoint/v1','repo':str(repo),'thread':'thread',
            'task_id':task,'owner':'owner','authority_revision':'AOS-001329',
            'step':'RED','code_files':['scripts/a.py'],'evidence_files':[]}
        file=evidence/'checkpoint.json';file.write_text(json.dumps(cp))
        return repo,context,cp,file

    def test_live_lease_and_file_changes_are_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file=self.setup_context(Path(d))
            a=checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)
            (repo/'scripts/a.py').write_text('value=2')
            b=checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)
            self.assertNotEqual(a['fingerprint'],b['fingerprint'])
            self.assertEqual(json.loads(file.read_text()),cp)

    def test_explicit_original_task_base_survives_authority_advance(self):
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file=self.setup_context(Path(d))
            cp.update(authority_revision='AOS-001330', task_base_revision='AOS-001329')
            (context/'memory/authority.json').write_text(json.dumps({'project_revision':'AOS-001330'}))
            file.write_text(json.dumps(cp))
            before={p:p.read_bytes() for p in (file,context/'memory/leases.json',
                context/'memory/receipts/tasks/task.json',context/'memory/authority.json')}
            result=checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)
            self.assertEqual(result['task_base_revision'],'AOS-001329')
            self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))

    def test_task_base_does_not_replace_current_authority_or_receipt(self):
        for change in ('missing_base','wrong_base','future_base','stale_authority'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as d:
                repo,context,cp,file=self.setup_context(Path(d))
                cp.update(authority_revision='AOS-001330',task_base_revision='AOS-001329')
                (context/'memory/authority.json').write_text(json.dumps({'project_revision':'AOS-001330'}))
                if change=='missing_base':cp.pop('task_base_revision')
                elif change=='wrong_base':cp['task_base_revision']='AOS-001328'
                elif change=='stale_authority':cp['authority_revision']='AOS-001329'
                else:
                    cp['task_base_revision']='AOS-001331'
                    receipt=json.loads((context/'memory/receipts/tasks/task.json').read_text())
                    receipt['base_revision']='AOS-001331'
                    (context/'memory/receipts/tasks/task.json').write_text(json.dumps(receipt))
                    (context/'memory/leases.json').write_text(json.dumps({'leases':[receipt]}))
                file.write_text(json.dumps(cp))
                with self.assertRaises(ValueError):
                    checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)

    def test_advanced_authority_still_requires_active_exact_owned_lease(self):
        for change in ('owner', 'expired', 'status', 'out_of_scope', 'malformed_base'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as d:
                repo,context,cp,file=self.setup_context(Path(d))
                cp.update(authority_revision='AOS-001330',task_base_revision='AOS-001329')
                (context/'memory/authority.json').write_text(json.dumps({'project_revision':'AOS-001330'}))
                receipt=json.loads((context/'memory/receipts/tasks/task.json').read_text())
                if change=='owner':cp['owner']='other'
                elif change=='expired':receipt['lease_expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
                elif change=='status':receipt['status']='COMPLETE'
                elif change=='out_of_scope':receipt['scope']=['aos-platform/apps']
                else:cp['task_base_revision']='AOS-1329'
                (context/'memory/receipts/tasks/task.json').write_text(json.dumps(receipt))
                (context/'memory/leases.json').write_text(json.dumps({'leases':[receipt]}))
                file.write_text(json.dumps(cp))
                with self.assertRaises(ValueError):
                    checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)

    def test_bad_owner_and_missing_lease_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file=self.setup_context(Path(d))
            cp['owner']='other';file.write_text(json.dumps(cp))
            with self.assertRaises(ValueError):checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)
            cp['owner']='owner';file.write_text(json.dumps(cp))
            (context/'memory/leases.json').write_text('{"leases":[]}')
            with self.assertRaises(ValueError):checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)

    def test_other_task_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file=self.setup_context(Path(d))
            cp['evidence_files']=['.evidence/other/output.txt'];file.write_text(json.dumps(cp))
            with self.assertRaises(ValueError):checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)

    def test_traversal_secret_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'scripts').mkdir();(root/'scripts/a.py').write_text('x')
            (root/'scripts/link.py').symlink_to(root/'scripts/a.py')
            for name in ('scripts/../scripts/a.py','scripts/credential.py','scripts/link.py'):
                with self.subTest(name=name),self.assertRaises(ValueError):exact_file(root,name,('scripts',))

class NativePackageCheckpointTest(unittest.TestCase):
    def native_context(self, root):
        repo,context,cp,file=CheckpointSafetyTest().setup_context(root)
        base=repo/'services/aos-api/postgres-extensions/native'
        base.mkdir(parents=True)
        files=[base/name for name in ('native.c','native.h','native.control','Makefile')]
        for path in files:path.write_text('initial native material\n')
        receipt=json.loads((context/'memory/receipts/tasks/task.json').read_text())
        receipt['scope']=['aos-platform/services/aos-api/postgres-extensions/native']
        (context/'memory/receipts/tasks/task.json').write_text(json.dumps(receipt))
        (context/'memory/leases.json').write_text(json.dumps({'leases':[receipt]}))
        cp['code_files']=[str(p.relative_to(repo)) for p in files]
        file.write_text(json.dumps(cp))
        return repo,context,cp,file,files

    def test_native_package_sources_control_and_makefile_are_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file,files=self.native_context(Path(d))
            watched=[file,context/'memory/authority.json',context/'memory/leases.json',context/'memory/receipts/tasks/task.json']
            before={p:p.read_bytes() for p in watched}
            first=checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)
            for path in files:
                path.write_text('changed '+path.name+'\n')
                second=checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)
                self.assertNotEqual(first['fingerprint'],second['fingerprint'])
                first=second
            self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))

    def test_native_extension_does_not_expand_arbitrary_file_permissions(self):
        for name in ('library.so','manifest.json','Makefile.backup','credentials.c','linked.h','../../../other.control'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                repo,context,cp,file,files=self.native_context(Path(d))
                bad=files[0].parent/name
                bad.parent.mkdir(parents=True,exist_ok=True)
                if name=='linked.h':bad.symlink_to(files[0])
                else:bad.write_text('not admissible\n')
                cp['code_files']=[str(bad.relative_to(repo))];file.write_text(json.dumps(cp))
                with self.assertRaises(ValueError):checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file,files=self.native_context(Path(d))
            cp['owner']='other';file.write_text(json.dumps(cp))
            with self.assertRaises(ValueError):checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)

    def test_native_names_outside_extension_directory_remain_rejected(self):
        for name in ('other.c','other.h','other.control','Makefile'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                repo,context,cp,file,files=self.native_context(Path(d))
                path=repo/'services'/name;path.write_text('not an extension package\n')
                receipt=json.loads((context/'memory/receipts/tasks/task.json').read_text())
                receipt['scope']=['aos-platform/services']
                (context/'memory/receipts/tasks/task.json').write_text(json.dumps(receipt))
                (context/'memory/leases.json').write_text(json.dumps({'leases':[receipt]}))
                cp['code_files']=[str(path.relative_to(repo))];file.write_text(json.dumps(cp))
                with self.assertRaises(ValueError):checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)

    def test_native_only_git_change_counts_but_later_docs_do_not(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*args):return run(['git','-C',d,*args],check=True,capture_output=True,text=True).stdout.strip()
            git('init','-b','m1');git('config','user.name','test');git('config','user.email','test@invalid')
            base=Path(d)/'services/aos-api/postgres-extensions/native';base.mkdir(parents=True)
            for name in ('native.c','native.h','native.control','Makefile'):
                (base/name).write_text('new '+name+'\n');git('add',str((base/name).relative_to(d)));git('commit','-m',name)
                self.assertEqual(snapshot(Path(d),'thread')['code_commit'],git('rev-parse','HEAD'))
            original=snapshot(Path(d),'thread')['code_commit']
            (base/'notes.md').write_text('docs\n');git('add','.');git('commit','-m','docs')
            self.assertEqual(snapshot(Path(d),'thread')['code_commit'],original)

class RecoveryGuidanceTest(unittest.TestCase):
    def decide(self, **kwargs):
        values=dict(user_paused=False,mechanism_authorized=False,active_tool=False,ownership_known=True,
                    outcome='read_only',risk='local',review_available=True,independent_candidate=True)
        values.update(kwargs);return recovery_guidance(**values)

    def test_latest_pause_wins(self):
        self.assertEqual(self.decide(user_paused=True),'RESPECT_USER_PAUSE')
        self.assertEqual(self.decide(user_paused=True,mechanism_authorized=True),'REVIEW_NEXT_SAFE_STEP')

    def test_existing_tool_and_ambiguous_owner_prevent_takeover(self):
        self.assertEqual(self.decide(active_tool=True),'WAIT_EXISTING_TOOL')
        self.assertEqual(self.decide(ownership_known=False),'RECONCILE_OWNERSHIP')

    def test_unknown_effect_never_resends(self):
        self.assertEqual(self.decide(outcome='unknown_external'),'RECONCILE_RECEIPT_ONLY')

    def test_unavailable_review_gates_only_formal_action(self):
        self.assertEqual(self.decide(risk='formal',review_available=False),'CONTINUE_INDEPENDENT_CANDIDATE')
        self.assertEqual(self.decide(risk='formal',review_available=False,independent_candidate=False),'FORMAL_ACTION_GATED')
        self.assertEqual(self.decide(review_available=False),'REVIEW_NEXT_SAFE_STEP')

class FixedRecoveryCasesTest(unittest.TestCase):
    def test_registered_incident_cases(self):
        data=json.loads((Path(__file__).parent/'fixtures/recovery_cases.json').read_text())
        self.assertEqual(data['schema'],'aos-recovery-cases/v1')
        self.assertEqual(len({c['id'] for c in data['cases']}),12)
        for case in data['cases']:
            with self.subTest(case=case['id'],partition=case['partition']):
                self.assertEqual(recovery_guidance(**case['input']),case['expected'])

class LongToolTest(unittest.TestCase):
    def current(self, state):
        return dict(repo='/repo',thread='thread',branch='m1',head='a',code_commit='a',code_time=100,
                    checkpoint={'task_id':'task','owner':'owner','authority_revision':'AOS-001329',
                                'step':'test','fingerprint':'same','command_state':state})

    def test_live_tool_does_not_allow_takeover(self):
        self.assertEqual(observe({},self.current('ACTIVE'),'001',3000)['action'],'WAIT_EXISTING_TOOL')

    def test_unknown_effect_requires_reconciliation(self):
        self.assertEqual(observe({},self.current('UNKNOWN_EXTERNAL'),'001',3000)['action'],'RECONCILE_RECEIPT_ONLY')

    def test_expired_or_lost_tool_requires_review_not_takeover(self):
        for state in ('EXPIRED','IDENTITY_MISMATCH','EXIT_UNRECONCILED'):
            self.assertEqual(observe({},self.current(state),'001',3000)['action'],'REVIEW_REQUIRED')

class ActualProcessIdentityTest(unittest.TestCase):
    def command(self):
        ident=process_identity(os.getpid())
        return dict(status='RUNNING',pid=os.getpid(),started=ident['started'],comm=ident['comm'],
                    deadline_at=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat())

    def test_current_process_verified_without_args(self):
        self.assertEqual(command_observation(self.command(),datetime.now(timezone.utc).timestamp()),'ACTIVE')

    def test_reused_identity_and_expired_bound_do_not_kill(self):
        c=self.command();c['started']='wrong-generation'
        self.assertEqual(command_observation(c,0),'IDENTITY_MISMATCH')
        c=self.command();c['deadline_at']='2000-01-01T00:00:00+00:00'
        self.assertEqual(command_observation(c,datetime.now(timezone.utc).timestamp()),'EXPIRED')
        self.assertIsNotNone(process_identity(os.getpid()))

    def test_naive_deadline_rejected(self):
        c=self.command();c['deadline_at']='2026-10-04T00:00:00'
        with self.assertRaises(ValueError):command_observation(c,0)

class StepCheckpointTest(CheckpointSafetyTest):
    def setup_steps(self, root):
        import hashlib
        repo,context,cp,file=self.setup_context(root)
        output=repo/'.evidence/task/result.txt';output.write_text('local result')
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        proof={'schema':'aos-step-evidence/v1','task_id':'task','owner':'owner','step':'test',
               'input_files':{'scripts/a.py':digest(repo/'scripts/a.py')},
               'output_files':{'.evidence/task/result.txt':digest(output)},'exit_code':0}
        pf=repo/'.evidence/task/proof.json';pf.write_text(json.dumps(proof))
        cp['steps']=[{'id':'test','state':'VERIFIED_LOCAL','proof':'.evidence/task/proof.json'},
                     {'id':'review','state':'PENDING'}]
        file.write_text(json.dumps(cp))
        return repo,context,cp,file,proof,pf

    def read(self, repo, context):
        return checkpoint_snapshot(repo,'thread','.evidence/task/checkpoint.json',context)

    def test_valid_evidence_navigates_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file,proof,pf=self.setup_steps(Path(d))
            before={p:p.read_bytes() for p in (file,pf,repo/'.evidence/task/result.txt')}
            for _ in range(2):self.assertEqual(self.read(repo,context)['next_step'],'REVIEW_STEP:review')
            self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_invalid_proof_rejected(self):
        for change in ({'exit_code':1},{'exit_code':False},{'owner':'other'},
                       {'input_files':{}},{'output_files':{}}):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
                repo,context,cp,file,proof,pf=self.setup_steps(Path(d))
                proof.update(change);pf.write_text(json.dumps(proof))
                with self.assertRaises(ValueError):self.read(repo,context)
        for path in ('scripts/a.py','.evidence/task/result.txt'):
            with self.subTest(path=path),tempfile.TemporaryDirectory() as d:
                repo,context,cp,file,proof,pf=self.setup_steps(Path(d));(repo/path).write_text('changed')
                with self.assertRaises(ValueError):self.read(repo,context)

    def test_missing_duplicate_or_false_skip_rejected(self):
        for steps in ([{'id':'a','state':'VERIFIED_LOCAL'}],
                      [{'id':'a','state':'PENDING'},{'id':'a','state':'PENDING'}],
                      [{'id':'a','state':'NOT_APPLICABLE','reason':''}],
                      [{'id':'a','state':'DONE'}],[]):
            with self.subTest(steps=steps),tempfile.TemporaryDirectory() as d:
                repo,context,cp,file,proof,pf=self.setup_steps(Path(d));cp['steps']=steps;file.write_text(json.dumps(cp))
                with self.assertRaises(ValueError):self.read(repo,context)

    def test_unknown_and_all_local_are_not_execution_or_completion(self):
        with tempfile.TemporaryDirectory() as d:
            repo,context,cp,file,proof,pf=self.setup_steps(Path(d))
            cp['steps'][1]['state']='UNKNOWN_EXTERNAL';file.write_text(json.dumps(cp))
            self.assertEqual(self.read(repo,context)['next_step'],'RECONCILE_STEP_ONLY:review')
            cp['steps'][1]={'id':'review','state':'NOT_APPLICABLE','reason':'local CLI only'};file.write_text(json.dumps(cp))
            self.assertEqual(self.read(repo,context)['next_step'],'LOCAL_STEPS_RECORDED')

class ThreadTransferTest(unittest.TestCase):
    NEW = '01a13484-f019-7d82-94ce-812396db9124'
    OLD = '01a0e5ff-d1a0-70f2-828f-9fc997519d04'

    def cli(self, home, *args):
        import sys
        return run([sys.executable, str(Path(__file__).with_name('aos_wake_progress.py')),
                    '--event', '2026-10-05T00:20:00+08:00', *args],
                   env=dict(os.environ, CODEX_HOME=str(home)), capture_output=True, text=True)

    def test_current_binding_and_old_or_missing_caller_rejected_without_write(self):
        self.assertEqual(THREAD, self.NEW)
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            for args in [(), ('--thread', self.OLD)]:
                result = self.cli(home, *args)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(list(home.iterdir()), [])

    def test_new_progress_isolated_preserves_old_bytes_and_duplicate_state(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d); directory = home/'automations/aos-2'; directory.mkdir(parents=True)
            old = directory/'progress.json'; old.write_text(json.dumps({'thread': self.OLD, 'event': 'old'}))
            original = old.read_bytes()
            result = self.cli(home, '--thread', self.NEW)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = directory/('progress-' + self.NEW + '.json')
            self.assertTrue(state.is_file())
            before = state.read_bytes(); stamp = state.stat().st_mtime_ns
            self.assertEqual(json.loads(before)['thread'], self.NEW)
            result = self.cli(home, '--thread', self.NEW)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((state.read_bytes(), state.stat().st_mtime_ns), (before, stamp))
            self.assertEqual(old.read_bytes(), original)
            result = self.cli(home, '--thread', self.OLD)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(state.read_bytes(), before)
            self.assertEqual(old.read_bytes(), original)

    def test_old_checkpoint_not_adopted_by_new_thread(self):
        with tempfile.TemporaryDirectory() as d:
            repo, context, cp, file = CheckpointSafetyTest().setup_context(Path(d))
            cp['thread'] = self.OLD; file.write_text(json.dumps(cp))
            with self.assertRaises(ValueError):
                checkpoint_snapshot(repo, self.NEW, '.evidence/task/checkpoint.json', context)
            cp['thread'] = self.NEW; file.write_text(json.dumps(cp))
            self.assertEqual(checkpoint_snapshot(repo, self.NEW, '.evidence/task/checkpoint.json', context)['owner'], 'owner')


class SuccessorThreadCliTest(unittest.TestCase):
    CURRENT = '01a13484-f019-7d82-94ce-812396db9124'
    LEGACY = '01a107a2-e9e4-7670-bc44-1144fa9b27e2'

    def invoke(self, directory, thread, *, shadow=True):
        import sys
        command = [sys.executable, '-B', str(Path(__file__).with_name('aos_wake_progress.py')),
                   '--thread', thread, '--event', '2026-10-17T00:00:00Z']
        if shadow:
            command.append('--shadow')
        return run(command, capture_output=True, text=True, timeout=30,
                   env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
                        'CODEX_HOME': str(directory), 'LC_ALL': 'C'})

    def test_formal_successor_shadow_reports_identity_without_state_write(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.invoke(d, self.CURRENT)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value['thread'], self.CURRENT)
            self.assertIn('never work authorization', value['meaning'])
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_retired_and_foreign_callers_fail_before_state_creation(self):
        for thread in (self.LEGACY, '01a00000-0000-7000-8000-000000000000'):
            with self.subTest(thread=thread), tempfile.TemporaryDirectory() as d:
                result = self.invoke(d, thread, shadow=False)
                self.assertEqual(result.returncode, 2)
                self.assertIn('does not match current writer binding', result.stderr)
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_successor_observation_preserves_legacy_state_and_deduplicates_event(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d) / 'automations' / 'aos-2'
            parent.mkdir(parents=True)
            legacy = parent / ('progress-' + self.LEGACY + '.json')
            original = b'{"legacy":"keep original bytes and unknown history"}\n'
            legacy.write_bytes(original)
            result = self.invoke(d, self.CURRENT, shadow=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            current = parent / ('progress-' + self.CURRENT + '.json')
            first = current.read_bytes()
            repeated = self.invoke(d, self.CURRENT, shadow=False)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(current.read_bytes(), first)
            self.assertEqual(legacy.read_bytes(), original)
            self.assertFalse(legacy.with_suffix('.lock').exists())
            self.assertEqual(current.stat().st_mode & 0o777, 0o600)

if __name__=='__main__': unittest.main()
