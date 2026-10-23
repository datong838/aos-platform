"""Source/fake SQL contract only; no maintenance connection or real grants."""
import ast
from contextlib import contextmanager
import inspect
from pathlib import Path
import unittest

from psycopg.rows import dict_row
from aos_api.aip_skill_eval_finisher_bootstrap import install_skill_finisher_permissions


class Result:
    def __init__(self, value=None):
        self.value=value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class Connection:
    def __init__(self, head='a0v_161'):
        self.head=head;self.autocommit=False;self.row_factory=dict_row
        self.database='aos_m2_three_backend';self.cluster='987654321'
        self.role='aos_app';self.login='aos_app';self.isolation='serializable'
        self.owner='aos_app';self.rls=True;self.force=True;self.writer_update=False
        self.existing=False;self.login_role=False;self.member=False;self.acl=False;self.policy=False
        self.statements=[];self.transactions=0;self.commits=0;self.rollbacks=0

    def execute(self, statement, args=None):
        self.statements.append((statement,args))
        if 'current_user AS role,session_user AS login' in statement:
            return Result(dict(role=self.role,login=self.login,database=self.database,isolation=self.isolation))
        if 'pg_control_system()' in statement:return Result(dict(id=self.cluster))
        if 'SELECT version_num' in statement:return Result(dict(version_num=self.head))
        if 'SELECT c.oid,r.rolname' in statement:
            return Result([dict(oid=i,rolname=self.owner,relrowsecurity=self.rls,relforcerowsecurity=self.force) for i in (1,2)])
        if "has_column_privilege('aos_aip_eval_writer'" in statement:
            return Result(dict(unsafe=self.writer_update))
        if 'FROM pg_roles WHERE rolname=%s' in statement:
            return Result(dict(oid=17,rolcanlogin=self.login_role,rolinherit=False,rolsuper=False,
                rolbypassrls=False,rolcreaterole=False,rolcreatedb=False,rolreplication=False) if self.existing else None)
        if 'WHERE roleid=%s OR member=%s' in statement:return Result(dict(unsafe=self.member))
        if 'aclexplode' in statement:return Result(dict(unsafe=self.acl))
        if 'FROM pg_policy WHERE polname=ANY' in statement:return Result(dict(present=self.policy))
        if statement.startswith(('CREATE ROLE ','GRANT ','CREATE POLICY ')):return Result()
        raise AssertionError('unrecognized fake maintenance query')

    @contextmanager
    def transaction(self):
        self.transactions+=1
        yield

    def commit(self):
        self.commits+=1
        raise AssertionError('bootstrap must not commit')

    def rollback(self):
        self.rollbacks+=1
        raise AssertionError('bootstrap must not roll back the caller')


def invoke(conn, **options):
    return install_skill_finisher_permissions(conn,
        expected_database=options.pop('expected_database','aos_m2_three_backend'),
        expected_cluster=options.pop('expected_cluster','987654321'),**options)


def ddl(conn):
    return [(s,a) for s,a in conn.statements if s.startswith(('CREATE ROLE ','GRANT ','CREATE POLICY '))]


class SchemaContractTests(unittest.TestCase):
    def test_default_161_contract_and_no_implicit_commit(self):
        conn=Connection();self.assertIsNone(invoke(conn))
        self.assertEqual((conn.transactions,conn.commits,conn.rollbacks),(1,0,0))
        self.assertEqual(sum(s.startswith('CREATE POLICY ') for s,_ in ddl(conn)),6)
        self.assertIn(('GRANT SELECT,UPDATE(status,version,started_at,finished_at) ON public.aip_eval_run TO aos_skill_eval_finisher',None),ddl(conn))

    def test_default_still_refuses_163_without_ddl(self):
        conn=Connection('a0v_163')
        with self.assertRaises(RuntimeError):invoke(conn)
        self.assertEqual(ddl(conn),[]);self.assertEqual(conn.transactions,0)

    def test_explicit_161_uses_identical_legacy_queries_and_grants(self):
        old,new=Connection(),Connection();invoke(old);invoke(new,expected_schema_head='a0v_161')
        self.assertEqual(old.statements,new.statements)

    def test_explicit_163_uses_identical_bounded_ddl(self):
        old,new=Connection(),Connection('a0v_163');invoke(old);invoke(new,expected_schema_head='a0v_163')
        self.assertEqual(old.statements,new.statements)
        self.assertEqual((new.commits,new.rollbacks,new.transactions),(0,0,1))

    def test_cross_schema_mismatch_has_no_fallback_or_mutation(self):
        for expected,actual in [('a0v_161','a0v_163'),('a0v_163','a0v_161')]:
            with self.subTest(expected=expected,actual=actual):
                conn=Connection(actual)
                with self.assertRaises(RuntimeError):invoke(conn,expected_schema_head=expected)
                self.assertEqual(ddl(conn),[]);self.assertEqual(conn.transactions,0)

    def test_unknown_or_noncanonical_heads_fail_before_any_sql(self):
        class Derived(str):pass
        for value in [None,'','a0v_162','a0v_164','a0v_163 ',' a0v_163','a0v_163\n',True,163,[],{},Derived('a0v_163')]:
            with self.subTest(type=type(value).__name__):
                conn=Connection('a0v_163')
                with self.assertRaises(RuntimeError):invoke(conn,expected_schema_head=value)
                self.assertEqual(conn.statements,[])

    def test_connection_owner_rls_and_writer_negatives_hold_in_both_modes(self):
        for head in ['a0v_161','a0v_163']:
            for attr,value in [('autocommit',True),('row_factory',None),('database','other'),
                    ('cluster','other'),('role','aos_runtime'),('login','other'),('isolation','read committed'),
                    ('owner','postgres'),('rls',False),('force',False),('writer_update',True)]:
                with self.subTest(head=head,attribute=attr):
                    conn=Connection(head);setattr(conn,attr,value)
                    with self.assertRaises(RuntimeError):invoke(conn,expected_schema_head=head)
                    self.assertEqual(ddl(conn),[]);self.assertEqual(conn.transactions,0)

    def test_existing_role_membership_acl_and_collision_remain_refused(self):
        for head in ['a0v_161','a0v_163']:
            for attr in ['login_role','member','acl','policy']:
                with self.subTest(head=head,attribute=attr):
                    conn=Connection(head);conn.existing=True;setattr(conn,attr,True)
                    with self.assertRaises(RuntimeError):invoke(conn,expected_schema_head=head)
                    self.assertEqual(ddl(conn),[])

    def test_safe_unused_existing_role_does_not_get_created_or_assigned_members(self):
        for head in ['a0v_161','a0v_163']:
            conn=Connection(head);conn.existing=True;invoke(conn,expected_schema_head=head)
            self.assertFalse(any(s.startswith('CREATE ROLE ') for s,_ in ddl(conn)))
            self.assertFalse(any(s.startswith('GRANT aos_skill_eval_finisher ') for s,_ in ddl(conn)))
            self.assertEqual(sum(s.startswith('CREATE POLICY ') for s,_ in ddl(conn)),6)
            self.assertEqual((conn.commits,conn.rollbacks),(0,0))

    def test_explicit_signature_and_original_native_fixture_scope_are_preserved(self):
        signature=inspect.signature(install_skill_finisher_permissions)
        self.assertEqual(signature.parameters['expected_schema_head'].default,'a0v_161')
        self.assertEqual(signature.parameters['expected_schema_head'].kind,inspect.Parameter.KEYWORD_ONLY)
        old=Path(__file__).with_name('test_skill_eval_finisher_bootstrap_pg.py').read_text()
        tree=ast.parse(old);choices=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='parametrize':
                if n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='scenario':
                    choices=ast.literal_eval(n.args[1])
        self.assertEqual(len(choices),13)
        self.assertTrue({'commit','rollback','writer-update','owner-drift','unknown-role-policy'}<=set(choices))
        self.assertIn('port',old);self.assertIn('18431',old)
