"""Nested whole-group consumers must not multiply stack by twelve controls."""
import pytest
pytest_plugins=('test_analysis_snapshot_native_claims_pg',)


def test_twelve_member_nested_current_consumers_have_bounded_stack(native_claims_case):
    conn,claims,args,_,_=native_claims_case
    owner=claims._groups
    def consume(level):
        return owner.run_current(conn,scope=args['scope'],actor=args['actor'],
            refs=tuple(ref for ref,_ in args['bindings']),
            execute=lambda group:consume(level-1) if level else len(group.members))
    assert consume(7)==12


def test_common_window_is_checked_after_the_callback(native_claims_case,monkeypatch):
    from datetime import timedelta
    import aos_api.pipeline_snapshot_group_owner as module
    conn,claims,args,_,_=native_claims_case
    clock=module._now
    end=[]
    monkeypatch.setattr(module,'_now',lambda db:end[0] if end else clock(db))
    def expire(group):
        end.append(group.expires_at+timedelta(seconds=1))
        return 'not-authorized-to-escape'
    with pytest.raises(PermissionError,match='common window'):
        claims._groups.run_current(conn,scope=args['scope'],actor=args['actor'],
            refs=tuple(ref for ref,_ in args['bindings']),execute=expire)


def test_group_consumer_cannot_escape_as_generator(native_claims_case):
    conn,claims,args,_,_=native_claims_case
    def deferred(group):
        yield group
    with pytest.raises(ValueError,match='locked transaction'):
        claims._groups.run_current(conn,scope=args['scope'],actor=args['actor'],
            refs=tuple(ref for ref,_ in args['bindings']),execute=deferred)
