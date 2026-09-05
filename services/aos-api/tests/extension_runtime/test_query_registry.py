import hashlib
import pytest

from aos_api.extension_runtime.query_registry import validate_select_template


def check(query):
    raw=query.encode()
    return validate_select_template(raw,expected_hash="sha256:"+hashlib.sha256(raw).hexdigest(),
        tables={"domain.products":frozenset({"id","name","price"})},parameter_count=1)


def test_explicit_columns_and_parameter_predicate():
    accepted=check("SELECT id, name FROM domain.products WHERE price >= $1")
    assert accepted.table=="domain.products"
    assert accepted.columns==("id","name")
    assert accepted.predicate_column=="price"
    assert accepted.operator==">="


@pytest.mark.parametrize("query",[
    "SELECT pg_sleep($1)","SELECT * FROM domain.products WHERE id=$1",
    "SELECT name FROM domain.products; DELETE FROM domain.products",
    "WITH x AS (DELETE FROM domain.products RETURNING *) SELECT * FROM x",
    "SELECT name INTO secret FROM domain.products WHERE id=$1",
    "SELECT name FROM domain.products WHERE id=$1 FOR UPDATE",
    "SELECT name FROM other.products WHERE id=$1",
    "SELECT secret FROM domain.products WHERE id=$1",
    "SELECT name FROM domain.products WHERE secret=$1",
    "SELECT name FROM domain.products WHERE id IN (SELECT $1)",
    "SELECT name FROM domain.products WHERE id=evil($1)",
    "SELECT name FROM domain.products WHERE id=$2",
    "SELECT name FROM domain.products WHERE id=$1 UNION SELECT name FROM domain.products",
    "SELECT name AS title FROM domain.products WHERE id=$1",
    "SELECT name FROM domain.products p WHERE id=$1",
    "SELECT name FROM domain.products WHERE id=$1 ORDER BY name",
    "SELECT name FROM domain.products WHERE id=$1::integer",
    "SELECT name FROM domain.products WHERE id OPERATOR(public.=) $1",
    "SELECT name FROM domain.products WHERE id=$1 OR id=$1",
])
def test_unsafe_or_unreviewed_shapes_are_rejected(query):
    with pytest.raises(ValueError):check(query)


def test_unsigned_bytes_rejected():
    with pytest.raises(ValueError):
        validate_select_template(b"SELECT id FROM domain.products WHERE id=$1",expected_hash="sha256:"+"0"*64,
            tables={"domain.products":frozenset({"id"})},parameter_count=1)


@pytest.mark.parametrize("count", [True, 0, 2, 33, "1"])
def test_parameter_contract_must_match(count):
    raw=b"SELECT id FROM domain.products WHERE id=$1"
    with pytest.raises(ValueError):
        validate_select_template(raw, expected_hash="sha256:"+hashlib.sha256(raw).hexdigest(),
            tables={"domain.products":frozenset({"id"})}, parameter_count=count)


def test_template_retains_exact_signed_bytes():
    sql="SELECT name FROM domain.products WHERE price >= $1; -- reviewed template"
    assert check(sql).sql==sql


@pytest.mark.parametrize("kind,value", [("int8", True), ("int8", 2**63),
    ("int8", "1"), ("text", object()), ("text", "x"*4097), ("text", "a\x00b"),
    ("bool", 1), ("jsonb", {}), ("int8", None)])
def test_parameter_values_cannot_escape_declared_type(kind, value):
    from aos_api.extension_runtime.query_registry import validate_parameter
    with pytest.raises(ValueError):
        validate_parameter(kind, value)


@pytest.mark.parametrize("kind,value", [("int8", 42), ("text", "栖月汇商品"), ("bool", False)])
def test_valid_parameter_identity(kind, value):
    from aos_api.extension_runtime.query_registry import validate_parameter
    assert validate_parameter(kind, value) == value
