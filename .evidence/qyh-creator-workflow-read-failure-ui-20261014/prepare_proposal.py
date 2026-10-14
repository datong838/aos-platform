from pathlib import Path
import difflib
E=Path(__file__).resolve().parent;R=E.parents[1]
p=R/'apps/web/src/components/workshop/CreatorGrowthPage.tsx';old=p.read_text();s=old
s=s.replace('function PreparationPanel({ purpose, products, current, receipt, history, busy, error,', 'function PreparationPanel({ purpose, products, current, receipt, history, busy, readUnavailable, error,',1)
s=s.replace('history: CreatorInternalWorkflowDraft[]; busy: boolean; error: string;', 'history: CreatorInternalWorkflowDraft[]; busy: boolean; readUnavailable: boolean; error: string;',1)
s=s.replace('const disabled = busy || values.title.length', 'const disabled = busy || readUnavailable || values.title.length',1)
s=s.replace('{current ? <section aria-label="当前草稿"><strong>{WORKFLOW_STATUS[current.status]}', '{readUnavailable ? <p role="alert">当前内部草稿暂未读取，暂存内容不能作为当前版本操作。请重新读取后再准备或评审。</p> : null}\n    {current ? <section aria-label={readUnavailable ? "上次读取草稿" : "当前草稿"}><strong>{readUnavailable ? "上次读取：" : ""}{WORKFLOW_STATUS[current.status]}',1)
s=s.replace('<small>写入基线 {current.version}', '<small>{readUnavailable ? "暂存版本" : "写入基线"} {current.version}',1)
# Only buttons within preparation/history, not global business fields or other flows.
a=s.index('function PreparationPanel(');b=s.index('const ADVISORS:',a)
s=s[:a]+s[a:b].replace('disabled={busy}', 'disabled={busy || readUnavailable}')+s[b:]
s=s.replace('  const workflowIntentKeys = useRef', '  const [workflowReadState, setWorkflowReadState] = useState<"loading" | "ready" | "failed">("loading");\n  const workflowIntentKeys = useRef',1)
s=s.replace('const id = ++request.current; setPhase("loading");', 'const id = ++request.current; setPhase("loading"); setWorkflowReadState("loading");',1)
s=s.replace('setWorkflowDrafts(latest); } setPhase("ready");', 'setWorkflowDrafts(latest); } setWorkflowReadState(workflows === null ? "failed" : "ready"); setPhase("ready");',1)
s=s.replace('if (id === request.current) setPhase(error instanceof', 'if (id === request.current) { setWorkflowReadState("failed"); setPhase(error instanceof',1)
s=s.replace('? "forbidden" : "failed"); }); };', '? "forbidden" : "failed"); } }); };',1)
s=s.replace('const activeDraft = preparation ? workflowDrafts[preparation] : undefined;', 'const activeDraft = preparation && workflowReadState === "ready" ? workflowDrafts[preparation] : undefined;',1)
s=s.replace('    if (!preparation) return;\n    const current', '    if (!preparation) return;\n    if (workflowReadState !== "ready") { setWorkflowError("当前内部草稿暂未读取，请重新读取后再操作。"); return; }\n    const current',1)
s=s.replace('    <div className="creator-growth-read-model">', '    {workflowReadState === "failed" ? <p role="alert">当前内部草稿暂未读取，请重新读取后再准备或评审。</p> : null}\n    <div className="creator-growth-read-model">',1)
s=s.replace(' busy={workflowBusy} error={workflowError}', ' busy={workflowBusy} readUnavailable={workflowReadState !== "ready"} error={workflowError}',1)
assert s!=old and 'readUnavailable={workflowReadState !== "ready"}' in s
(E/'proposed-page.tsx.txt').write_text(s)
(E/'proposed-diff-r1.txt').write_text(''.join(difflib.unified_diff(old.splitlines(keepends=True),s.splitlines(keepends=True),fromfile=str(p)+' CURRENT',tofile=str(p)+' PROSPECTIVE NOT APPLIED')))
print({'proposalBytes':len(s.encode()),'diffBytes':(E/'proposed-diff-r1.txt').stat().st_size,'productUnmodified':p.read_text()==old})
