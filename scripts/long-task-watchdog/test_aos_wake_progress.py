import tempfile
import unittest
from pathlib import Path
from subprocess import run
from aos_wake_progress import observe, snapshot, checkpoint_snapshot, exact_file, recovery_guidance, process_identity, command_observation
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
        receipt={'task_id':task,'owner':'owner','base_revision':'AOS-001329',
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

if __name__=='__main__': unittest.main()
