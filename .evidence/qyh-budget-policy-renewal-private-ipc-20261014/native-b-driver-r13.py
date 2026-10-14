from pathlib import Path
import json,tempfile
import pytest
from tests.aip.test_budget_policy_renewal_service import schema_database,schema_source
from tests.aip.test_budget_policy_renewal_service import isolated_signed_gateway,test_native_private_service_signed_chain_and_at_most_once
database=schema_database.__wrapped__();db=next(database)
source=schema_source.__wrapped__(db);data=next(source)
monkeypatch=pytest.MonkeyPatch()
with tempfile.TemporaryDirectory(prefix="owned-b-chain-") as temporary:
    gateway=isolated_signed_gateway.__wrapped__(data,Path(temporary),monkeypatch)
    try:
        actual=next(gateway)
        test_native_private_service_signed_chain_and_at_most_once(actual)
        print(json.dumps({"nativeBChainPass":True,"fixtureSignedJwtOnly":True,"noRealConsent":True,"originalVolumeTouched":False}))
    finally:
        try:next(gateway)
        except StopIteration:pass
        monkeypatch.undo()
        try:next(source)
        except StopIteration:pass
        try:next(database)
        except StopIteration:pass
