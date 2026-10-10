from pathlib import Path
import hashlib, importlib.util, json
repo=Path(__file__).resolve().parents[3]
base=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("wake",repo/"scripts/long-task-watchdog/aos_wake_progress.py")
wake=importlib.util.module_from_spec(spec);spec.loader.exec_module(wake)
context=repo.parent/"docs/palantier/AOS项目开发上下文"
relative=lambda p:str(p.relative_to(repo))
results={}
def rejected(name, document, expected):
    file=base/(name+".json");file.write_text(json.dumps(document,indent=2)+"\n")
    try: wake.checkpoint_snapshot(repo,wake.THREAD,relative(file),context)
    except ValueError as e:
        assert expected in str(e),(name,str(e));results[name]=str(e)
    else: raise AssertionError(name+" accepted")
old=json.loads((base/"checkpoint-before.json").read_text())
rejected("before-red",old,"invalid file list")
current=json.loads((base.parent/"checkpoint.json").read_text())
results["valid"]=wake.checkpoint_snapshot(repo,wake.THREAD,relative(base.parent/"checkpoint.json"),context)
for name,key,value,error in [
 ("wrong-thread","thread","wrong","checkpoint identity mismatch"),
 ("wrong-owner","owner","wrong","checkpoint has no current owned lease"),
 ("stale-authority","authority_revision","AOS-001754","checkpoint has no current owned lease"),
 ("foreign-evidence","evidence_files",[".evidence/foreign/result.json"],"evidence outside task directory"),
 ("unowned-code","code_files",["scripts/long-task-watchdog/aos_wake_progress.py"],"file outside task scope")]:
    mutated=current.copy();mutated[key]=value;rejected(name,mutated,error)
index=json.loads((base/"history-index.json").read_text())
assert list(index["files"])==old["evidence_files"]
for path,digest in index["files"].items():assert hashlib.sha256((repo/path).read_bytes()).hexdigest()==digest,path
assert current["code_files"]==old["code_files"]
assert len(current["evidence_files"])<=32
results.update(history_files_verified=len(index["files"]),current_evidence_count=len(current["evidence_files"]),status="CHECKPOINT_BOUND_REPAIR_GREEN",full_task_delivered=False,goal_complete=False,execution_allowed=False)
(base/"verification.json").write_text(json.dumps(results,indent=2)+"\n")
print(json.dumps(results))
