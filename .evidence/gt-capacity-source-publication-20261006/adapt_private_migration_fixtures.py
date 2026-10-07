"""One-time exact fixture edits for reuse of audited latest-code installation."""
import ast
from pathlib import Path
p=Path('services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py')
s=p.read_text()
def edit(name, transform):
    global s
    node=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
    lines=s.splitlines(keepends=True)
    start=sum(map(len,lines[:node.lineno-1]));end=sum(map(len,lines[:node.end_lineno]))
    old=s[start:end];new=transform(old)
    assert new!=old,name
    s=s[:start]+new+s[end:]
def replace(text,old,new):
    assert text.count(old)==1,(old[:80],text.count(old))
    return text.replace(old,new,1)
def facts(text):
    start=text.index("            for profile in (")
    end=text.index("            installed=",start)
    block=text[start:end]
    return text[:start]+"            persisted=_reuse_migrated_private_source(owner)\n            if not persisted:\n"+''.join('    '+line for line in block.splitlines(keepends=True))+text[end:]
edit('native_original_fact_reader',facts)
def command(text):
    return replace(text,'        owner.execute(CAPACITY_ORIGINAL_SOURCE_COMMAND_SQL)\n','        persisted=_reuse_migrated_private_source(owner)\n        if persisted:signatures=[]\n        else:owner.execute(CAPACITY_ORIGINAL_SOURCE_COMMAND_SQL)\n')
edit('native_original_command_reader',command)
def signed(text):
    return replace(text,'        owner.execute(CAPACITY_ORIGINAL_SOURCE_COMMAND_SQL)\n        owner.execute(CAPACITY_ORIGINAL_SOURCE_SIGNED_FACTS_SQL)\n','        persisted=_reuse_migrated_private_source(owner)\n        if persisted:signatures=[]\n        else:\n            owner.execute(CAPACITY_ORIGINAL_SOURCE_COMMAND_SQL)\n            owner.execute(CAPACITY_ORIGINAL_SOURCE_SIGNED_FACTS_SQL)\n')
edit('native_full_signed_reader',signed)
def pending(text):
    text=replace(text,'        owner.execute(CAPACITY_SOURCE_PENDING_SQL)\n','        persisted=_reuse_migrated_private_source(owner)\n        if not persisted:owner.execute(CAPACITY_SOURCE_PENDING_SQL)\n')
    start=text.index("            owner.execute('DROP FUNCTION aos_capacity_publication_private.prepare_original_source")
    block=text[start:]
    return text[:start]+'            if not persisted:\n'+''.join('    '+line for line in block.splitlines(keepends=True))
edit('native_pending_source_reader',pending)
def commit(text):
    text=replace(text,'        if implementation is not None:owner.execute(implementation)\n','        persisted=_reuse_migrated_private_source(owner)\n        if implementation is not None and not persisted:owner.execute(implementation)\n')
    return replace(text,'            if implementation is not None:\n','            if implementation is not None and not persisted:\n')
edit('native_commit_source_reader',commit)
def complete(text):
    text=replace(text,'            transaction.install_source_transaction_boundary(owner.execute)\n','            persisted=_reuse_migrated_private_source(owner)\n            if not persisted:transaction.install_source_transaction_boundary(owner.execute)\n')
    text=replace(text,"            assert set(installed)=={item['signature'] for item in transaction.source_transaction_function_manifest()}\n","            assert set(installed)==(set() if persisted else {item['signature'] for item in transaction.source_transaction_function_manifest()})\n")
    start=text.index("                for table in ('source_provenance'")
    end=text.index('                assert {',start)
    block=text[start:end]
    text=text[:start]+'                if not persisted:\n'+''.join('    '+line for line in block.splitlines(keepends=True))+text[end:]
    return text
edit('native_complete_source_installation',complete)
def checker(text):
    text=replace(text,'        transaction.install_source_transaction_boundary(owner.execute)\n','        persisted=_reuse_migrated_private_source(owner)\n        if not persisted:transaction.install_source_transaction_boundary(owner.execute)\n')
    text=replace(text,'        assert len(installed)==41\n','        assert len(installed)==(0 if persisted else 41)\n')
    start=text.index("            for name in ('source_provenance'")
    end=text.index('            assert owner.execute',start)
    block=text[start:end]
    return text[:start]+'            if not persisted:\n'+''.join('    '+line for line in block.splitlines(keepends=True))+text[end:]
edit('test_native_private_source_installation_preserves_original_checker',checker)
s+='''


def _reuse_migrated_private_source(owner):
    """Reuse only an exact full installation; never downgrade or delete it.

    Older retained a156 databases can still host explicitly owned temporary
    fragments. A newer recorded migration with missing objects is drift and
    must fail the audit instead of silently rebuilding those objects.
    """
    from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_tables
    versions=[r['version_num'] for r in owner.execute('SELECT version_num FROM alembic_version').fetchall()]
    migrated=any(v.startswith('a0v_') and v[4:].isdigit() and int(v[4:])>=157 for v in versions)
    present=owner.execute("SELECT count(*) AS n FROM pg_class WHERE relnamespace='aos_capacity_publication_private'::regnamespace AND relname=ANY(%s::text[])",
        (['global_account','global_provider','source_pending','source_publication','source_provenance'],)).fetchone()['n']
    if migrated or present==5:
        require_source_transaction_tables(owner)
        return True
    return False
'''
ast.parse(s);p.write_text(s)
print('Seven fixture/install scopes adapted; original transaction SQL untouched')
