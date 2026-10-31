import unittest
from unittest.mock import patch
from aos_review import (SYSTEM, PINNED_REPAIR_KIND, PINNED_REPAIR_SCHEMA,
                        _apply_exact_quote_repair,
                        _pinned_evidence_quote_positions,
                        apply_pinned_quote_repair, consumption_record,
                        load_repair_context,
                        parse_response, prime_command, reconciled_result_envelope,
                        strict_json_loads, validate_result)
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
        request=self.request()
        return {'request_id':request['request_id'],'task_id':request['task_id'],
                'owner':request['owner'],'kind':request['kind'],'baseline':request['baseline'],
                'verdict':'PASS','findings':[{'claim':'No tool execution permitted',
                    'evidence':'fixed no-tools flag','assessment':'supported'}],
                'next_safe_step':'Review only'}

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

    def test_extra_result_or_finding_fields_are_rejected(self):
        result=self.result();result['claims']=self.request()['claims']
        with self.assertRaises(ValueError):validate_result(self.request(),result)
        result=self.result();result['findings'][0]['line']=1
        with self.assertRaises(ValueError):validate_result(self.request(),result)

    def test_host_disables_all_discovery_and_tools(self):
        cmd=prime_command('/tmp/review','/approved/node')
        for flag in ('--no-tools','--no-extensions','--no-skills','--no-context-files','--no-session','--offline'):
            self.assertIn(flag,cmd)
        self.assertNotIn('--api-key',cmd)
        self.assertEqual(cmd[0],'/approved/node')

    def test_fixed_runtime_candidate_requires_regular_executable_current_node(self):
        from aos_review import resolve_node_runtime
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);node=root/'node'
            node.write_text('#!/bin/sh\nprintf "v24.22.1\\n"\n');node.chmod(0o700)
            self.assertEqual(resolve_node_runtime((str(node),)),str(node))
            link=root/'node-link';link.symlink_to(node)
            with self.assertRaises(ValueError):resolve_node_runtime((str(link),))
            node.write_text('#!/bin/sh\nprintf "v18.0.0\\n"\n');node.chmod(0o700)
            with self.assertRaises(ValueError):resolve_node_runtime((str(node),))

    def test_runtime_resolution_precedes_attempt_marker(self):
        import aos_review
        source=Path(aos_review.__file__).read_text()
        self.assertLess(source.index('node = resolve_node_runtime()'),
                        source.index("attempt = parent /"))

class ReviewTransportTest(unittest.TestCase):
    def test_system_prompt_requires_strict_json_quote_hygiene(self):
        self.assertIn('不得返回Markdown代码围栏', SYSTEM)
        self.assertIn('ASCII双引号必须JSON转义', SYSTEM)
        self.assertIn('禁止自动修复坏JSON', SYSTEM)

    def test_system_prompt_requires_complete_top_level_contract(self):
        self.assertIn('输出前逐项检查顶层字段', SYSTEM)
        self.assertIn('next_safe_step必须是非空字符串', SYSTEM)

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

    def test_exact_whole_message_json_fence_is_unwrapped(self):
        value={'verdict':'NEED_EVIDENCE'}
        event={'type':'message_end','message':{'role':'assistant','content':[{
            'type':'text','text':'```json\n'+json.dumps(value)+'\n```'}]}}
        self.assertEqual(parse_response(json.dumps(event)),value)

    def test_fence_with_prose_or_multiple_fences_is_rejected(self):
        values=('prefix\n```json\n{}\n```','```json\n{}\n```\nsuffix',
                '```json\n{}\n```\n```json\n{}\n```','```\n{}\n```')
        for value in values:
            event={'type':'message_end','message':{'role':'assistant','content':[{
                'type':'text','text':value}]}}
            with self.subTest(value=value),self.assertRaises((ValueError,json.JSONDecodeError)):
                parse_response(json.dumps(event))

    def test_unescaped_source_quotes_inside_json_string_remain_rejected(self):
        malformed='{"verdict":"PASS","evidence":"ValueError("invalid terminal facts")"}'
        event={'type':'message_end','message':{'role':'assistant','content':[{
            'type':'text','text':malformed}]}}
        with self.assertRaises(json.JSONDecodeError):
            parse_response(json.dumps(event))

    def test_correctly_escaped_source_quotes_inside_json_string_are_accepted(self):
        value={'verdict':'PASS','evidence':'ValueError("invalid terminal facts")'}
        event={'type':'message_end','message':{'role':'assistant','content':[{
            'type':'text','text':json.dumps(value)}]}}
        self.assertEqual(parse_response(json.dumps(event)),value)

    def test_strict_decoder_rejects_duplicate_nonfinite_and_trailing_values(self):
        for text in ('{"a":1,"a":2}','{"a":NaN}','{} {}','{} trailing'):
            with self.subTest(text=text),self.assertRaises((ValueError,json.JSONDecodeError)):
                strict_json_loads(text)


class PinnedQuoteRepairTest(unittest.TestCase):
    def request(self):
        return ReviewContractTest().request()

    def malformed_text(self, unicode_prefix=''):
        result=ReviewContractTest().result()
        result['findings'][0]['evidence']=unicode_prefix+'frozen `state "open"` evidence'
        valid=json.dumps(result,ensure_ascii=False,indent=2)
        return valid.replace(r'state \"open\"', 'state "open"')

    def transport(self, text):
        return {'returncode':0,'stdout':json.dumps({'type':'message_end','message':{
            'role':'assistant','content':[{'type':'text','text':text}]}})}

    def permit_and_bindings(self, text, transport=None, positions=None):
        transport=transport or self.transport(text)
        if positions is None:
            start=text.index('`state ')+len('`state ')
            positions=[start,start+len('"open')]
        window=16
        repaired=''.join(('\\' if index in set(positions) else '')+char
                         for index,char in enumerate(text))
        digest=lambda value:hashlib.sha256(value).hexdigest()
        bindings={'request_sha256':digest(b'request'),'transport_sha256':digest(b'transport'),
                  'stdout_sha256':digest(transport['stdout'].encode()),
                  'permit_sha256':digest(b'permit')}
        permit={'schema':PINNED_REPAIR_SCHEMA,'policy_version':1,
                'repair_kind':PINNED_REPAIR_KIND,
                'request_sha256':bindings['request_sha256'],
                'transport_sha256':bindings['transport_sha256'],
                'stdout_sha256':bindings['stdout_sha256'],
                'assistant_text_sha256':digest(text.encode()),
                'repaired_text_sha256':digest(repaired.encode()),'window_chars':window,
                'positions':[{'char_offset':position,
                              'byte_offset':len(text[:position].encode()),
                              'before_sha256':digest(text[max(0,position-window):position].encode()),
                              'after_sha256':digest(text[position+1:position+1+window].encode())}
                             for position in positions],
                'max_repairs':len(positions),'model_reinvoked':False,
                'execution_authorized':False}
        return permit,bindings

    def repair(self, text):
        permit,bindings=self.permit_and_bindings(text)
        return _apply_exact_quote_repair(text,permit,bindings)

    def test_exact_permit_repairs_only_pinned_inline_evidence_quotes(self):
        text=self.malformed_text()
        result,metadata=self.repair(text)
        self.assertEqual(result['findings'][0]['evidence'],'frozen `state "open"` evidence')
        self.assertEqual(result['verdict'],'PASS')
        self.assertEqual(metadata['repair_kind'],PINNED_REPAIR_KIND)
        self.assertIs(metadata['model_reinvoked'],False)

    def test_valid_json_and_generic_missing_comma_are_never_repaired(self):
        valid=json.dumps(ReviewContractTest().result(),indent=2)
        permit,bindings=self.permit_and_bindings(self.malformed_text())
        permit['assistant_text_sha256']=hashlib.sha256(valid.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'forbidden for valid JSON'):
            _apply_exact_quote_repair(valid,permit,bindings)
        missing_comma='{"evidence":"fixed" "assessment":"supported"}'
        with self.assertRaises(json.JSONDecodeError):strict_json_loads(missing_comma)

    def test_any_binding_hash_position_window_or_repaired_hash_drift_fails_closed(self):
        text=self.malformed_text();permit,bindings=self.permit_and_bindings(text)
        mutations=(('binding',lambda p,b:b.update(request_sha256='0'*64)),
                   ('position',lambda p,b:p['positions'][0].update(char_offset=0)),
                   ('window',lambda p,b:p['positions'][0].update(before_sha256='0'*64)),
                   ('repaired',lambda p,b:p.update(repaired_text_sha256='0'*64)))
        for name,mutate in mutations:
            candidate=json.loads(json.dumps(permit));candidate_bindings=dict(bindings)
            mutate(candidate,candidate_bindings)
            with self.subTest(name=name),self.assertRaises(ValueError):
                _apply_exact_quote_repair(text,candidate,candidate_bindings)

    def test_quotes_outside_balanced_evidence_inline_code_are_rejected(self):
        text=self.malformed_text().replace('`state "open"`','state "open"')
        permit,bindings=self.permit_and_bindings(self.malformed_text())
        permit['assistant_text_sha256']=hashlib.sha256(text.encode()).hexdigest()
        with self.assertRaises(ValueError):_apply_exact_quote_repair(text,permit,bindings)
        unbalanced=self.malformed_text().replace('` evidence',' evidence')
        permit,bindings=self.permit_and_bindings(unbalanced)
        with self.assertRaisesRegex(ValueError,'unbalanced'):
            _apply_exact_quote_repair(unbalanced,permit,bindings)

    def test_unicode_char_and_byte_offsets_are_distinct_and_enforced(self):
        text=self.malformed_text('中文')
        permit,bindings=self.permit_and_bindings(text)
        self.assertNotEqual(permit['positions'][0]['char_offset'],permit['positions'][0]['byte_offset'])
        result,_=_apply_exact_quote_repair(text,permit,bindings)
        self.assertEqual(result['findings'][0]['evidence'],'中文frozen `state "open"` evidence')
        permit['positions'][0]['byte_offset']=permit['positions'][0]['char_offset']
        with self.assertRaisesRegex(ValueError,'byte position mismatch'):
            _apply_exact_quote_repair(text,permit,bindings)

    def test_reconcile_and_consume_require_the_same_exact_repair_replay(self):
        request=self.request();text=self.malformed_text();transport=self.transport(text)
        permit,bindings=self.permit_and_bindings(text,transport)
        bindings['approval_consumption_sha256']='a'*64
        repair={'permit':permit,'bindings':bindings}
        frozen={'request_sha256':bindings['request_sha256'],
                'transport_sha256':bindings['transport_sha256'],
                'stdout_sha256':bindings['stdout_sha256'],
                'assistant_text_sha256':permit['assistant_text_sha256'],
                'repaired_text_sha256':permit['repaired_text_sha256'],
                'permit_sha256':bindings['permit_sha256'],
                'positions':tuple(entry['char_offset'] for entry in permit['positions'])}
        with patch('aos_review.PINNED_REPAIR_ALLOWLIST',frozen):
            envelope=reconciled_result_envelope(request,transport,'current',repair=repair)
            self.assertIn('syntax_repair',envelope)
            record=consumption_record(request,envelope,transport,'current',repair=repair)
            self.assertEqual(record['status'],'CONSUMED_MATERIAL_REVIEW')
            with self.assertRaisesRegex(ValueError,'requires exact permit replay'):
                consumption_record(request,envelope,transport,'current')
            valid_transport=ConsumptionTest().transport()
            unrepaired=reconciled_result_envelope(request,valid_transport,'current')
            with self.assertRaisesRegex(ValueError,'cannot consume an unrepaired'):
                consumption_record(request,unrepaired,valid_transport,'current',repair=repair)

    def test_missing_comma_candidate_field_cannot_be_swallowed_into_evidence(self):
        result=ReviewContractTest().result()
        valid=json.dumps(result,ensure_ascii=False,indent=2)
        text=valid.replace('"evidence": "fixed no-tools flag"',
            '"evidence": "frozen `" "note": "x` evidence"')
        positions=_pinned_evidence_quote_positions(text)
        self.assertEqual(len(positions),4)
        permit,bindings=self.permit_and_bindings(text,positions=positions)
        with self.assertRaisesRegex(ValueError,'not an approved frozen repair tuple'):
            apply_pinned_quote_repair(text,permit,bindings)

    def test_baseline_evidence_field_cannot_be_a_repair_target(self):
        request=ReviewContractTest().request()
        request['baseline']['evidence']='frozen `state "open"` evidence'
        result=ReviewContractTest().result();result['baseline']=request['baseline']
        valid=json.dumps(result,ensure_ascii=False,indent=2)
        text=valid.replace(r'state \"open\"','state "open"')
        positions=_pinned_evidence_quote_positions(text)
        permit,bindings=self.permit_and_bindings(text,positions=positions)
        with self.assertRaisesRegex(ValueError,'not an approved frozen repair tuple'):
            apply_pinned_quote_repair(text,permit,bindings)

    def test_repair_text_and_candidate_counts_are_bounded_before_quadratic_work(self):
        text=self.malformed_text()+(' '*(128*1024))
        permit,bindings=self.permit_and_bindings(text)
        with self.assertRaisesRegex(ValueError,'exceeds bounded size'):
            _apply_exact_quote_repair(text,permit,bindings)
        crowded='  "evidence": "frozen `'+('" '*65)+'` evidence",\n'
        with self.assertRaisesRegex(ValueError,'too many'):
            _pinned_evidence_quote_positions(crowded,64)


class FrozenP07IntegrationTest(unittest.TestCase):
    def fixture(self):
        root=Path(__file__).resolve().parents[2]
        evidence=root/'.evidence/qyh-m2-terminal-source-implementation-20261025/successor-review-r521'
        request_file=evidence/'successor-review-f01-p07-request-r521.json'
        transport_file=evidence/'successor-review-f01-p07-result-r521.transport.json'
        permit_file=evidence/'successor-review-f01-p07-repair-permit-r527.json'
        request=json.loads(request_file.read_text())
        transport=json.loads(transport_file.read_text())
        permit=json.loads(permit_file.read_text())
        from aos_review import extract_response_text
        text=extract_response_text(transport['stdout'])
        digest=lambda value:hashlib.sha256(value).hexdigest()
        bindings={'request_sha256':digest(request_file.read_bytes()),
                  'transport_sha256':digest(transport_file.read_bytes()),
                  'stdout_sha256':digest(transport['stdout'].encode()),
                  'permit_sha256':digest(permit_file.read_bytes())}
        return request,transport,permit,text,bindings,evidence

    def test_real_32_position_p07_exact_transform_is_valid_before_authority_gate(self):
        request,_,permit,text,bindings,_,=self.fixture()
        result,metadata=_apply_exact_quote_repair(text,permit,bindings)
        validate_result(request,result)
        self.assertEqual(result['verdict'],'PASS')
        self.assertEqual(len(metadata['char_positions']),32)
        self.assertEqual(tuple(metadata['char_positions']),
                         tuple(entry['char_offset'] for entry in permit['positions']))

    def test_real_p07_cannot_pass_public_gate_without_independent_approval(self):
        _,_,permit,text,bindings,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'independently consumed approval'):
            apply_pinned_quote_repair(text,permit,bindings)
        bindings=dict(bindings,request_sha256='0'*64,
                      approval_consumption_sha256='a'*64)
        with self.assertRaisesRegex(ValueError,'not an approved frozen repair tuple'):
            apply_pinned_quote_repair(text,permit,bindings)

    def test_real_p07_independent_approval_replays_before_public_repair(self):
        request,_,_,_,_,evidence=self.fixture()
        repo=Path(__file__).resolve().parents[2]
        request_relative=str((evidence/'successor-review-f01-p07-request-r521.json').relative_to(repo))
        transport_relative=str((evidence/'successor-review-f01-p07-result-r521.transport.json').relative_to(repo))
        permit_relative=str((evidence/'successor-review-f01-p07-repair-permit-r527.json').relative_to(repo))
        approval_relative=str((evidence/'successor-review-f01-p07-repair-approval-r529.json').relative_to(repo))
        from aos_review import validate_request
        selected=validate_request(repo,request,request_path=request_relative)
        receipt_path=(repo.parent/'docs/palantier/AOS项目开发上下文/memory/receipts/tasks'/
                      (request['task_id']+'.json'))
        receipt=json.loads(receipt_path.read_text())
        request_bytes=(repo/request_relative).read_bytes()
        transport,repair=load_repair_context(
            repo,receipt,selected,request_bytes,transport_relative,permit_relative,approval_relative)
        from aos_review import extract_response_text
        result,metadata=apply_pinned_quote_repair(
            extract_response_text(transport['stdout']),repair['permit'],repair['bindings'])
        self.assertEqual(result['verdict'],'PASS')
        self.assertRegex(metadata['approval_consumption_sha256'],r'^[0-9a-f]{64}$')

    def test_real_p07_saved_reconcile_and_consumption_replay_exactly(self):
        request,_,_,_,_,evidence=self.fixture()
        repo=Path(__file__).resolve().parents[2]
        rel=lambda name:str((evidence/name).relative_to(repo))
        request_relative=rel('successor-review-f01-p07-request-r521.json')
        receipt=json.loads((repo.parent/'docs/palantier/AOS项目开发上下文/memory/receipts/tasks'/
                            (request['task_id']+'.json')).read_text())
        from aos_review import validate_request
        selected=validate_request(repo,request,request_path=request_relative)
        transport,repair=load_repair_context(
            repo,receipt,selected,(repo/request_relative).read_bytes(),
            rel('successor-review-f01-p07-result-r521.transport.json'),
            rel('successor-review-f01-p07-repair-permit-r527.json'),
            rel('successor-review-f01-p07-repair-approval-r529.json'))
        envelope=json.loads((evidence/'successor-review-f01-p07-result-r521.json').read_text())
        saved=json.loads((evidence/'successor-review-f01-p07-consumption-r521.json').read_text())
        import aos_review
        runner_hash=hashlib.sha256(Path(aos_review.__file__).read_bytes()).hexdigest()
        replayed=consumption_record(request,envelope,transport,runner_hash,repair=repair)
        self.assertEqual(replayed,saved)
        self.assertEqual(saved['status'],'CONSUMED_MATERIAL_REVIEW')

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

    def prepare_successor_evidence(self, root):
        repo,req,m=self.prepare(root)
        receipt=json.loads((m/'receipts/tasks/t1.json').read_text())
        receipt['task_id']='successor-t1'
        receipt['scope']=['aos-platform/.evidence/original-t1']
        (m/'receipts/tasks/t1.json').unlink()
        (m/'receipts/tasks/successor-t1.json').write_text(json.dumps(receipt))
        (m/'leases.json').write_text(json.dumps({'leases':[receipt]}))
        evidence=repo/'.evidence/original-t1';evidence.mkdir(parents=True)
        (evidence/'material.txt').write_text('bounded review material')
        req.update(task_id='successor-t1',baseline=dict(req['baseline'],files={
            '.evidence/original-t1/material.txt':hashlib.sha256(b'bounded review material').hexdigest()}),
            materials={'.evidence/original-t1/material.txt':'bounded review material'})
        return repo,req,receipt

    def test_successor_may_use_exact_old_named_evidence_root_from_current_scope(self):
        with tempfile.TemporaryDirectory() as d:
            repo,req,_=self.prepare_successor_evidence(Path(d))
            self.assertIsNotNone(validate_request(
                repo,req,request_path='.evidence/original-t1/review-request.json'))

    def test_unlisted_or_mixed_evidence_root_is_rejected(self):
        from aos_review import select_evidence_root
        with tempfile.TemporaryDirectory() as d:
            _,_,receipt=self.prepare_successor_evidence(Path(d))
            selected=select_evidence_root(
                receipt,'successor-t1','.evidence/original-t1/review-request.json')
            self.assertEqual(selected,Path('.evidence/original-t1'))
            with self.assertRaises(ValueError):
                select_evidence_root(receipt,'successor-t1','.evidence/not-owned/result.json')
            with self.assertRaises(ValueError):
                select_evidence_root(
                    receipt,'successor-t1','.evidence/successor-t1/result.json',selected)

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

    def test_normal_review_transport_has_dedicated_16_mib_bound(self):
        from aos_review import review_transport_file
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'.evidence').mkdir();file=root/'.evidence/review.transport.json'
            with file.open('wb') as stream:stream.truncate(16*1024*1024)
            self.assertEqual(review_transport_file(root,'.evidence/review.transport.json'),file)
            with file.open('wb') as stream:stream.truncate(16*1024*1024+1)
            with self.assertRaises(ValueError):review_transport_file(root,'.evidence/review.transport.json')

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

    def test_exact_predecessor_runner_remains_consumable_after_bound_fix(self):
        from aos_review import consumption_record
        envelope=self.envelope()
        envelope['runner_sha256']='872f17e86dbfbb970d150ca1f3342d972e14d9236e6621dfc17111f9c963a969'
        record=consumption_record(self.request(),envelope,self.transport(),'new-current')
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

    def test_existing_transport_can_form_envelope_without_model_reinvoke(self):
        from aos_review import reconciled_result_envelope
        envelope=reconciled_result_envelope(self.request(),self.transport(),'current')
        self.assertEqual(envelope['result'],self.result())
        self.assertIs(envelope['execution_authorized'],False)
        self.assertIs(envelope['model_reinvoked'],False)
        self.assertRegex(envelope['reconciled_transport_sha256'],r'^[0-9a-f]{64}$')

if __name__=='__main__':unittest.main()
