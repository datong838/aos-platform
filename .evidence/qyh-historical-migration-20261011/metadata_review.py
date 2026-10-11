import ast,hashlib,importlib.util,json,re,sys
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('sql_tools',R.parent/'qyh-org-name-maintenance-20261011'/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
m.R=R;m.DB='aos_meta_head';TARGET='aos-qyh-history-restore-20261011'
manifest=json.loads((R/'code-manifest.json').read_text());path=json.loads((R.parent/'qyh-historical-full-restore-20261011'/'migration-path.json').read_text())['steps']
expected=[]
for entry in path:
    number=int(entry['revision'].split('_')[-1]);file=Path(entry['file']).resolve();raw=file.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==entry['sha256']==manifest[str(file.relative_to(R.parents[1]))]
    tree=ast.parse(raw);constants={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            try:value=ast.literal_eval(node.value)
            except (ValueError,TypeError):continue
            for t in node.targets:
                if isinstance(t,ast.Name):constants[t.id]=value
    def literal(node):
        if isinstance(node,ast.Constant):return node.value
        if isinstance(node,ast.JoinedStr):return ''.join(str(constants[v.value.id]) if isinstance(v,ast.FormattedValue) and isinstance(v.value,ast.Name) else str(v.value) if isinstance(v,ast.Constant) else '' for v in node.values)
        return ''
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute) or node.func.attr!='execute' or not node.args:continue
        try:sql=literal(node.args[0])
        except KeyError:continue
        match=re.fullmatch(r'\s*INSERT INTO public\.(meta_object_type|meta_action_type)\s*\(([^)]+)\)\s*VALUES\s*(.+?)\s*',sql,re.S)
        if not match:continue
        table,columns,values=match.groups()
        assert re.fullmatch(r'[a-z_,\s]+',columns)
        data=json.loads(m.psql(TARGET,m.DB,'BEGIN READ ONLY; SELECT json_agg(row_to_json(v)) FROM (VALUES '+values+') AS v('+columns+'); COMMIT;'))
        for row in data:
            for field in ('properties','required_markings','parameters','submission_criteria'):
                if field in row and isinstance(row[field],str):row[field]=json.loads(row[field])
            expected.append({'step':number,'table':'public.'+table,'fields':row,'sourceSha256':entry['sha256']})
assert len(expected)==16
m.record('metadata-expectations.json',expected)
print(json.dumps({'expectedMetadataAdditions':len(expected),'migrationSteps':sorted({r['step'] for r in expected})}))
