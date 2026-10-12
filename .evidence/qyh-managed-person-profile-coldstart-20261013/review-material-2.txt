from contextlib import contextmanager

import pytest

from aos_api import db, person_identity as person, tenant_catalog


@pytest.fixture
def profiles(monkeypatch):
    monkeypatch.setattr(tenant_catalog, 'persistence_enabled', lambda: True)
    monkeypatch.setattr(person, '_PERSONS', {})
    return monkeypatch


def test_persisted_profile_survives_cold_cache_with_native_readonly_connection(profiles):
    with db.connect_platform() as conn:
        assert conn.info.dbname.startswith('aos_test_')
        conn.execute("INSERT INTO twa_person_profile(subject,display_name,title) VALUES(%s,%s,%s)",
                     ('human:cold-profile-test', 'Persisted administrator', 'Administrator'))
        conn.commit()
    assert person.get_profile('human:cold-profile-test')['displayName'] == 'human:cold-profile-test'
    observed = []
    @contextmanager
    def readonly(**kwargs):
        assert kwargs == {'inherit_scope': False, 'platform_role': True}
        with db.connect_read_only(**kwargs) as conn:
            assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
            observed.append(True)
            yield conn
    profiles.setattr(person, 'connect_read_only', readonly, raising=False)
    assert person.load_profiles_from_db(strict=True) >= 1
    assert observed == [True]
    assert person.get_profile('human:cold-profile-test')['displayName'] == 'Persisted administrator'
    assert person.get_profile('human:cold-profile-test')['email'] is None
    with db.connect_platform() as conn:
        assert conn.execute("SELECT count(*) AS n FROM twa_person_profile WHERE subject=%s", ('human:cold-profile-test',)).fetchone()['n'] == 1


def test_failed_strict_load_preserves_existing_cache(profiles):
    person._PERSONS['preserved'] = {'subject': 'preserved', 'displayName': 'Existing'}
    @contextmanager
    def unavailable(**kwargs):
        raise RuntimeError('profile catalog unavailable')
        yield
    profiles.setattr(person, 'connect_read_only', unavailable, raising=False)
    with pytest.raises(RuntimeError, match='profile catalog unavailable'):
        person.load_profiles_from_db(strict=True)
    assert person.get_profile('preserved')['displayName'] == 'Existing'
    assert person.load_profiles_from_db() == 0
    assert person.get_profile('preserved')['displayName'] == 'Existing'


def test_memory_mode_never_connects_or_replaces_profile(profiles):
    profiles.setattr(tenant_catalog, 'persistence_enabled', lambda: False)
    person._PERSONS['preserved'] = {'subject': 'preserved', 'displayName': 'Existing'}
    def forbidden(**kwargs):
        raise AssertionError('memory mode must never connect')
    profiles.setattr(person, 'connect_read_only', forbidden, raising=False)
    assert person.load_profiles_from_db(strict=True) == 0
    assert person.get_profile('preserved')['displayName'] == 'Existing'


def test_invalid_row_never_publishes_a_partial_profile_cache(profiles):
    person._PERSONS['preserved'] = {'subject': 'preserved', 'displayName': 'Existing'}
    class Connection:
        def execute(self, query):
            assert query.startswith('SELECT ') and 'FROM twa_person_profile' in query
            return self
        def fetchall(self):
            return [dict(subject='new', display_name='New', email=None, phone=None, title=None),
                    dict(subject='', display_name='Invalid', email=None, phone=None, title=None)]
    @contextmanager
    def readonly(**kwargs):
        yield Connection()
    profiles.setattr(person, 'connect_read_only', readonly)
    with pytest.raises(ValueError, match='invalid persisted person subject'):
        person.load_profiles_from_db(strict=True)
    assert set(person._PERSONS) == {'preserved'}
