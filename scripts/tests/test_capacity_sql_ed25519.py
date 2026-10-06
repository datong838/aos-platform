"""Native verifier checks against a separately registered, disposable PG instance."""
import json
import os
import subprocess

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


CONTEXT = "colima-aos-a0v-test-only"
DATABASE = "aos_test_ed25519"


@pytest.fixture(scope="module")
def target():
    name = os.environ["AOS_CRYPTO_TEST_CONTAINER"]
    image = os.environ["AOS_CRYPTO_TEST_IMAGE"]
    assert name.startswith("aos-ed25519-test-")
    result = subprocess.run(
        ["docker", "--context", CONTEXT, "inspect", name],
        text=True, capture_output=True, check=True,
    )
    state = json.loads(result.stdout)[0]
    assert state["Image"] == image
    assert state["HostConfig"]["NetworkMode"] == "none"
    assert not state["HostConfig"]["PortBindings"]
    assert not state["HostConfig"]["Privileged"]
    assert state["Config"]["Labels"]["aos.task"] == "gt-capacity-sql-ed25519-20261006"
    mounts = state["Mounts"]
    assert len(mounts) == 1
    assert mounts[0]["Type"] == "volume"
    assert mounts[0]["Name"] == name + "-data"
    assert mounts[0]["Destination"] == "/var/lib/postgresql/data"
    return name


def sql(target, statement, success=True):
    result = subprocess.run(
        ["docker", "--context", CONTEXT, "exec", "-i", target,
         "psql", "-U", "aos_app", "-d", DATABASE, "-Atq",
         "-v", "ON_ERROR_STOP=1", "-f", "-"],
        input=statement, text=True, capture_output=True, timeout=60,
    )
    if success:
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    assert result.returncode != 0
    return result.stderr


def bytea(value):
    return "'\\x" + value.hex() + "'::bytea"


def signed(message):
    private = Ed25519PrivateKey.generate()
    return private.sign(message), private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def verify(target, signature, message, key):
    return sql(target, "SELECT aos_ed25519.verify(%s,%s,%s);" %
               (bytea(signature), bytea(message), bytea(key)))


def test_install_owner_drift_rejected(target):
    error = sql(target, "BEGIN; CREATE ROLE aos_ed25519_owner LOGIN; CREATE EXTENSION aos_ed25519;", False)
    assert "AOS_ED25519_OWNER_DRIFT" in error
    assert sql(target, "SELECT count(*) FROM pg_roles WHERE rolname='aos_ed25519_owner';") == "0"
    error = sql(target, "BEGIN; CREATE ROLE aos_ed25519_owner NOLOGIN NOINHERIT; CREATE TYPE untrusted_owner_type AS ENUM ('x'); ALTER TYPE untrusted_owner_type OWNER TO aos_ed25519_owner; CREATE EXTENSION aos_ed25519;", False)
    assert "AOS_ED25519_OWNER_DRIFT" in error
    assert sql(target, "SELECT count(*) FROM pg_roles WHERE rolname='aos_ed25519_owner';") == "0"


def test_install_and_catalog(target):
    sql(target, "CREATE EXTENSION aos_ed25519;")
    assert sql(target, """
SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
JOIN pg_language l ON l.oid=p.prolang
WHERE n.nspname='aos_ed25519' AND p.proname='verify'
AND p.proowner='aos_ed25519_owner'::regrole AND l.lanname='c'
AND p.proisstrict AND NOT p.prosecdef AND NOT p.proleakproof
AND p.provolatile='i' AND p.proparallel='s' AND p.pronargs=3
AND p.proargtypes='17 17 17'::oidvector AND p.prorettype=16;
""") == "1"
    assert sql(target, """
SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
LATERAL aclexplode(p.proacl) a WHERE n.nspname='aos_ed25519' AND a.grantee=0;
""") == "0"


@pytest.mark.parametrize("message", [b"", b"hello", b"\x00\xff\x80", "容量许可".encode()])
def test_independent_signatures_and_mutations(target, message):
    signature, key = signed(message)
    assert verify(target, signature, message, key) == "t"
    assert verify(target, bytes([signature[0] ^ 1]) + signature[1:], message, key) == "f"
    assert verify(target, signature, message + b"x", key) == "f"
    _, other = signed(message)
    assert verify(target, signature, message, other) == "f"


def test_rfc8032_empty_message_vector(target):
    # RFC 8032 section 7.1, TEST 1; public verification material only.
    key = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    signature = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    assert verify(target, signature, b"", key) == "t"


@pytest.mark.parametrize("signature_size,key_size", [(0,32),(63,32),(65,32),(64,0),(64,31),(64,33)])
def test_bad_lengths(target, signature_size, key_size):
    assert verify(target, b"s" * signature_size, b"", b"k" * key_size) == "f"


def test_null_is_never_permission(target):
    assert sql(target, "SELECT aos_ed25519.verify(NULL,NULL,NULL) IS NULL, aos_ed25519.verify(NULL,NULL,NULL) IS TRUE;") == "t|f"


@pytest.mark.parametrize("storage", ["EXTENDED", "EXTERNAL"])
def test_toasted_message_boundary(target, storage):
    message = b"a" * (2 * 1024 * 1024)
    signature, key = signed(message)
    assert sql(target, """
BEGIN;
CREATE TEMP TABLE verifier_input(message bytea);
ALTER TABLE verifier_input ALTER COLUMN message SET STORAGE %s;
INSERT INTO verifier_input VALUES (%s);
SELECT octet_length(message), aos_ed25519.verify(%s,message,%s),
  pg_column_size(message) < octet_length(message) FROM verifier_input;
ROLLBACK;
""" % (storage, bytea(message), bytea(signature), bytea(key))) == (
        "2097152|t|t" if storage == "EXTENDED" else "2097152|t|f"
    )
    oversized = message + b"a"
    assert sql(target, """
BEGIN;
CREATE TEMP TABLE verifier_input(message bytea);
ALTER TABLE verifier_input ALTER COLUMN message SET STORAGE %s;
INSERT INTO verifier_input VALUES (%s);
SELECT octet_length(message), aos_ed25519.verify(%s,message,%s),
  pg_column_size(message) < octet_length(message) FROM verifier_input;
ROLLBACK;
""" % (storage, bytea(oversized), bytea(signature), bytea(key))) == (
        "2097153|f|t" if storage == "EXTENDED" else "2097153|f|f"
    )


def test_readonly_and_repeated_calls(target):
    signature, key = signed(b"safe")
    assert sql(target, "BEGIN READ ONLY; SELECT bool_and(aos_ed25519.verify(%s,%s,%s)) FROM generate_series(1,1000); COMMIT;" %
               (bytea(signature), bytea(b"safe"), bytea(key))) == "t"
    assert sql(target, "BEGIN READ ONLY; SELECT bool_and(NOT aos_ed25519.verify(%s,%s,%s)) FROM generate_series(1,1000); COMMIT;" %
               (bytea(b"\x00" * 64), bytea(b"safe"), bytea(key))) == "t"
    assert verify(target, signature, b"safe", key) == "t"
    assert sql(target, "BEGIN READ ONLY; SELECT bool_and(NOT aos_ed25519.verify(%s,%s,%s)) FROM generate_series(1,1000); SELECT aos_ed25519.verify(%s,%s,%s); COMMIT;" %
               (bytea(b"\x00" * 64), bytea(b"safe"), bytea(key),
                bytea(signature), bytea(b"safe"), bytea(key))) == "t\nt"


def test_private_owner_and_schema(target):
    assert sql(target, """
SELECT NOT (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
FROM pg_roles WHERE rolname='aos_ed25519_owner';
SELECT count(*) FROM pg_auth_members WHERE roleid='aos_ed25519_owner'::regrole OR member='aos_ed25519_owner'::regrole;
SELECT nspowner='aos_ed25519_owner'::regrole FROM pg_namespace WHERE nspname='aos_ed25519';
SELECT count(*) FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE n.nspname='aos_ed25519' AND a.grantee=0;
SELECT extversion,extrelocatable FROM pg_extension WHERE extname='aos_ed25519';
SELECT probin,prosrc FROM pg_proc WHERE oid='aos_ed25519.verify(bytea,bytea,bytea)'::regprocedure;
""") == "t\n0\nt\n0\n1.0|f\n$libdir/aos_ed25519|aos_ed25519_verify"


def test_explicit_role_grant_only(target):
    signature, key = signed(b"scoped")
    call = "SELECT aos_ed25519.verify(%s,%s,%s);" % (bytea(signature),bytea(b"scoped"),bytea(key))
    error = sql(target, "BEGIN; CREATE ROLE verifier_reader NOLOGIN; SET LOCAL ROLE verifier_reader; " + call, False)
    assert "permission denied for schema aos_ed25519" in error
    error = sql(target, "BEGIN; CREATE ROLE verifier_reader NOLOGIN; GRANT USAGE ON SCHEMA aos_ed25519 TO verifier_reader; SET LOCAL ROLE verifier_reader; " + call, False)
    assert "permission denied for function verify" in error
    assert sql(target, "BEGIN; CREATE ROLE verifier_reader NOLOGIN; GRANT USAGE ON SCHEMA aos_ed25519 TO verifier_reader; GRANT EXECUTE ON FUNCTION aos_ed25519.verify(bytea,bytea,bytea) TO verifier_reader; SET LOCAL ROLE verifier_reader; " + call + " ROLLBACK;") == "t"
