import unittest
from aos_review import validate_result, prime_command, parse_response
import json
import tempfile
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
from aos_review import validate_request

class ReviewContractTest(unittest.TestCase):
    def request(self):
        return {'request_id':'r1','task_id':'t1','owner':'developer','kind':'quality',
                'baseline':{'head':'a','authority_revision':'AOS-001329','files':{'f':'hash'}},
                'claims':['No tool execution permitted']}

    def result(self):
        return dict(self.request(),verdict='PASS',findings=[{'claim':'No tool execution permitted',
                    'evidence':'fixed no-tools flag','assessment':'supported'}],next_safe_step='Review only')

    def test_empty_pass_rejected(self):
        result=self.result();result['findings']=[]
        with self.assertRaises(ValueError): validate_result(self.request(),result)

    def test_wrong_head_rejected(self):
        result=self.result();result['baseline']=dict(result['baseline'],head='b')
        with self.assertRaises(ValueError): validate_result(self.request(),result)

    def test_wrong_request_rejected(self):
        result=self.result();result['request_id']='other'
        with self.assertRaises(ValueError): validate_result(self.request(),result)

    def test_pass_requires_all_claims(self):
        req=self.request();req['claims'].append('other claim')
        with self.assertRaises(ValueError):validate_result(req,self.result())

    def test_valid_review_is_scoped_not_execution_permission(self):
        self.assertIsNone(validate_result(self.request(),self.result()))

    def test_host_disables_all_discovery_and_tools(self):
        cmd=prime_command('/tmp/review')
        for flag in ('--no-tools','--no-extensions','--no-skills','--no-context-files','--no-session','--offline'):
            self.assertIn(flag,cmd)
        self.assertNotIn('--api-key',cmd)

class ReviewTransportTest(unittest.TestCase):
    def test_isolated_settings_prevent_internal_retry_and_background_work(self):
        import aos_review
        with tempfile.TemporaryDirectory() as cwd:
            aos_review.prepare_review_directory(cwd)
            settings=json.loads((Path(cwd)/'.prime/agent/settings.json').read_text())
            self.assertEqual(settings['retry'], {'enabled':False,'maxRetries':0,
                             'provider':{'maxRetries':0,'timeoutMs':110000}})
            for key in ('compaction','autoRefine','telemetry'):
                self.assertIs(settings[key]['enabled'],False)

    def test_zero_process_exit_cannot_hide_auth_failure(self):
        stream=json.dumps({'type':'message_end','message':{'role':'assistant','stopReason':'error',
                                                         'errorMessage':'401 invalid identity','content':[]}})
        with self.assertRaisesRegex(ValueError,'REVIEW_AUTH_REQUIRED'):parse_response(stream)

    def test_tool_call_or_execution_rejected(self):
        for event in [{'type':'tool_execution_start'}, {'type':'message_end','message':{'role':'assistant',
                      'content':[{'type':'toolCall','name':'write'}]}}]:
            with self.subTest(event=event),self.assertRaises(ValueError):parse_response(json.dumps(event))

    def test_valid_terminal_json_extracted(self):
        value={'verdict':'NEED_EVIDENCE'}
        event={'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':json.dumps(value)}]}}
        self.assertEqual(parse_response(json.dumps(event)),value)

    def test_textual_json_without_assistant_event_rejected(self):
        with self.assertRaises(ValueError):parse_response(json.dumps({'verdict':'PASS'}))

class ReviewBaselineIntegrationTest(unittest.TestCase):
    def prepare(self, root):
        repo=root/'aos-platform';repo.mkdir()
        def git(*args):
            return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,text=True).stdout.strip()
        git('init','-b','m1');git('config','user.name','fixture');git('config','user.email','fixture@invalid')
        (repo/'scripts').mkdir();(repo/'scripts/check.py').write_text('value=1')
        git('add','scripts/check.py');git('commit','-m','fixture')
        m=root/'docs/palantier/AOS项目开发上下文/memory';(m/'receipts/tasks').mkdir(parents=True)
        receipt={'task_id':'t1','owner':'developer','base_revision':'AOS-001329',
                 'lease_expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                 'scope':['aos-platform/scripts'],'excluded_scope':[]}
        (m/'authority.json').write_text(json.dumps({'project_revision':'AOS-001329'}))
        (m/'leases.json').write_text(json.dumps({'leases':[receipt]}))
        (m/'receipts/tasks/t1.json').write_text(json.dumps(receipt))
        req={'schema':'aos-material-review/v1','request_id':'r1','task_id':'t1','owner':'developer','kind':'quality',
             'baseline':{'head':git('rev-parse','HEAD'),'authority_revision':'AOS-001329',
                         'files':{'scripts/check.py':hashlib.sha256(b'value=1').hexdigest()}},
             'claims':['value initially one'],'materials':{'scripts/check.py':'value=1'}}
        return repo,req,m

    def test_recheck_rejects_change_after_initial_validation(self):
        with tempfile.TemporaryDirectory() as d:
            repo,req,m=self.prepare(Path(d));validate_request(repo,req)
            (repo/'scripts/check.py').write_text('value=2')
            with self.assertRaisesRegex(ValueError,'changed material'):validate_request(repo,req)

    def test_no_lease_and_wrong_owner_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            repo,req,m=self.prepare(Path(d));req['owner']='other'
            with self.assertRaises(ValueError):validate_request(repo,req)
            req['owner']='developer';(m/'leases.json').write_text('{"leases":[]}')
            with self.assertRaises(ValueError):validate_request(repo,req)

    def test_excluded_scope_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            repo,req,m=self.prepare(Path(d));receipt=json.loads((m/'receipts/tasks/t1.json').read_text())
            receipt['excluded_scope']=['aos-platform/scripts']
            (m/'receipts/tasks/t1.json').write_text(json.dumps(receipt))
            (m/'leases.json').write_text(json.dumps({'leases':[receipt]}))
            with self.assertRaisesRegex(ValueError,'excluded scope'):validate_request(repo,req)

class ConsumptionTest(unittest.TestCase):
    def test_transport_has_explicit_bounded_limit_without_relaxing_material_limit(self):
        from aos_wake_progress import exact_file
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'.evidence').mkdir();file=root/'.evidence/review.transport.json'
            with file.open('wb') as stream:stream.truncate(2*1024*1024)
            with self.assertRaises(ValueError):exact_file(root,'.evidence/review.transport.json',('.evidence',))
            self.assertEqual(exact_file(root,'.evidence/review.transport.json',('.evidence',),max_bytes=8*1024*1024),file)
            with file.open('wb') as stream:stream.truncate(8*1024*1024+1)
            with self.assertRaises(ValueError):exact_file(root,'.evidence/review.transport.json',('.evidence',),max_bytes=8*1024*1024)

    def request(self):
        return ReviewContractTest().request()

    def result(self):
        return ReviewContractTest().result()

    def envelope(self):
        return {'schema':'aos-material-review-result/v1','mode':'tools-disabled-material-only',
                'execution_authorized':False,'runner_sha256':'current','result':self.result()}

    def transport(self):
        return {'returncode':0,'stdout':json.dumps({'type':'message_end',
                'message':{'role':'assistant','content':[{'type':'text','text':json.dumps(self.result())}]}})}

    def test_current_review_can_be_consumed_without_execution_permission(self):
        from aos_review import consumption_record
        record=consumption_record(self.request(),self.envelope(),self.transport(),'current')
        self.assertEqual(record['status'],'CONSUMED_MATERIAL_REVIEW')
        self.assertIs(record['execution_authorized'],False)

    def test_old_runner_or_privilege_flag_rejected(self):
        from aos_review import consumption_record
        for patch in ({'runner_sha256':'old'},{'execution_authorized':True}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                consumption_record(self.request(),dict(self.envelope(),**patch),self.transport(),'current')

    def test_envelope_cannot_replace_transport_verdict(self):
        from aos_review import consumption_record
        envelope=self.envelope();envelope['result']=dict(self.result(),next_safe_step='fabricated suggestion')
        with self.assertRaisesRegex(ValueError,'differs from actual transport'):
            consumption_record(self.request(),envelope,self.transport(),'current')

    def test_result_must_match_real_transport(self):
        from aos_review import consumption_record
        t=self.transport();t['stdout']=json.dumps({'type':'message_end','message':{'role':'assistant','stopReason':'error','errorMessage':'401','content':[]}})
        with self.assertRaisesRegex(ValueError,'REVIEW_AUTH_REQUIRED'):
            consumption_record(self.request(),self.envelope(),t,'current')

if __name__=='__main__':unittest.main()
