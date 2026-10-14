"""Prime supported system-prompt adapter; unchanged strict AOS result gates."""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'scripts/long-task-watchdog'))
import aos_review as gate

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path,value):
    with path.open('x') as stream:
        os.chmod(path,0o600);json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.flush();os.fsync(stream.fileno())

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--request',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--consume')
    args=parser.parse_args()
    request=gate.json.loads(gate.exact_file(REPO,args.request,('.evidence',)).read_text())
    assert request['task_id']=='qyh-restoration-readonly-continuation-r3-20261014'
    prefix='.evidence/'+request['task_id']+'/'
    assert args.request.startswith(prefix) and args.output.startswith(prefix)
    output=Path(args.output)
    assert not output.is_absolute() and '..' not in output.parts and output.suffix=='.json'
    parent=REPO
    for part in output.parts[:-1]:
        parent=parent/part
        assert not parent.is_symlink() and parent.is_dir()
    target=REPO/output;assert target.parent.is_dir() and not target.exists()
    gate.validate_request(REPO,request)
    own_sha=digest(Path(__file__));validator_sha=digest(Path(gate.__file__))
    if args.consume:
        assert args.consume.startswith(prefix)
        envelope=json.loads(gate.exact_file(REPO,args.consume,('.evidence',)).read_text())
        transport=json.loads(gate.exact_file(REPO,str(Path(args.consume).with_suffix('.transport.json')),('.evidence',),max_bytes=8*1024*1024).read_text())
        assert envelope['validator_sha256']==validator_sha
        record=gate.consumption_record(request,envelope,transport,own_sha)
        gate.validate_request(REPO,request)
        marker=target.parent/(hashlib.sha256(request['request_id'].encode()).hexdigest()+'.consumed.json')
        save(marker,record);save(target,record)
        print(json.dumps({'consumption':str(target),'status':record['status'],'execution_authorized':False}));return
    for prior in target.parent.glob('*.attempt.json'):
        assert json.loads(prior.read_text())['request_id']!=request['request_id'],'existing attempt: reconcile, do not resend'
    marker=target.parent/(hashlib.sha256(request['request_id'].encode()).hexdigest()+'.attempt.json')
    save(marker,{'request_id':request['request_id'],'baseline':request['baseline'],'status':'ATTEMPTED_UNKNOWN','runner_sha256':own_sha,'validator_sha256':validator_sha})
    template={k:request[k] for k in ('request_id','task_id','owner','kind','baseline')}
    template.update(verdict='<choose PASS/REWORK/NEED_EVIDENCE/NEED_DECISION>',
        findings=[{'claim':c,'evidence':'<actual supplied file/function/field evidence; do not invent>','assessment':'<choose supported/contradicted/insufficient>'} for c in request['claims']],
        next_safe_step='<required concrete nonempty safe suggestion, even for PASS>')
    system=gate.SYSTEM+'\n篇幅合同：每个findings.evidence不超过600个字符，next_safe_step不超过250个字符；只保留定位与核心依据，不重复列出整份源码或叙述全部测试。不得省略任何claims的实际审阅或改变判断门。\n'+'\n输出协议硬要求：整个assistant文本第一个字符必须是{、最后一个字符必须是}。不要输出```或json代码围栏，不能输出JSON之前或之后的解释。以下仅为输出字段框架，标识/claims需逐字复制；它不是已经证明的事实，判定与证据必须实际审阅填写，不得将占位符原样输出。next_safe_step不可遗漏。\n'+json.dumps(template,ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix='aos-review-b-system-') as cwd:
        gate.prepare_review_directory(cwd)
        command=gate.prime_command(cwd)
        command[1:1]=['--dns-result-order=ipv4first','--require',str(REPO/'.evidence/qyh-creator-workflow-read-failure-ui-20261014/prime-undici-fetch-r2.cjs')]
        command[command.index('--system-prompt')+1]=system
        proc=subprocess.run(command,input=json.dumps(request,ensure_ascii=False),env={'HOME':str(Path.home()),'PATH':str(Path(gate.NODE).parent)+':/usr/bin:/bin','PRIME_AGENT_INTERNAL_LEGACY_OWNED_WORKER_FRONTEND':'1'},capture_output=True,text=True,timeout=120)
    gate.scan_secrets(proc.stdout);gate.scan_secrets(proc.stderr)
    transport={'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}
    save(target.with_suffix('.transport.json'),transport)
    assert proc.returncode==0,'terminal failure; reconcile, no automatic retry'
    result=gate.parse_response(proc.stdout)  # Exact raw JSON; NEVER strip fences or repair.
    gate.validate_result(request,result);gate.validate_request(REPO,request)
    assert digest(Path(__file__))==own_sha and digest(Path(gate.__file__))==validator_sha
    save(target,{'schema':'aos-material-review-result/v1','mode':'tools-disabled-material-only',
        'runner_sha256':own_sha,'validator_sha256':validator_sha,'execution_authorized':False,'network_connect_timeout_ms':60000,'review_model':'agnes-2.5-flash','result':result})
    print(json.dumps({'result':str(target),'verdict':result['verdict'],'execution_authorized':False}))

if __name__=='__main__':main()
