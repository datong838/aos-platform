"""Restricted, hash-bound SELECT templates. Validation does not authorize execution."""

from dataclasses import dataclass
import hashlib
from collections.abc import Mapping

from pglast import parse_sql


@dataclass(frozen=True)
class ValidatedSelect:
    sql: str
    table: str
    columns: tuple[str, ...]
    parameter_count: int
    predicate_column: str
    operator: str


def validate_parameter(kind: str, value):
    """Initial registry scalar types; no coercion or arbitrary DB adapters."""
    if kind == "int8" and type(value) is int and -(2**63) <= value < 2**63:
        return value
    if kind == "bool" and type(value) is bool:
        return value
    if kind == "text" and type(value) is str:
        try:
            valid = "\x00" not in value and len(value.encode("utf-8")) <= 4096
        except UnicodeEncodeError:
            valid = False
        if valid:
            return value
    raise ValueError("parameter does not match supported registry type")


def validate_select_template(
    raw: bytes, *, expected_hash: str,
    tables: Mapping[str, frozenset[str]], parameter_count: int,
) -> ValidatedSelect:
    """Accept only explicit single-table columns and parameter comparisons.

    The registry must independently authenticate its manifest, relation types,
    tenant policy and execution role. A matching digest alone is not a signature.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 65536:
        raise ValueError("invalid template size")
    if expected_hash != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise ValueError("template digest mismatch")
    if type(parameter_count) is not int or not 1 <= parameter_count <= 32:
        raise ValueError("invalid parameter count")
    try:
        sql = raw.decode("utf-8")
        statements = parse_sql(sql)
    except Exception as exc:
        raise ValueError("invalid SQL template") from exc
    if len(statements) != 1:
        raise ValueError("exactly one statement required")
    root = statements[0].stmt(skip_none=True)
    allowed = {"@", "targetList", "fromClause", "whereClause", "groupDistinct",
               "limitOption", "op", "all"}
    if (root.get("@") != "SelectStmt" or set(root) - allowed
            or root.get("groupDistinct") or root.get("all")
            or root.get("op", {}).get("name") != "SETOP_NONE"
            or root.get("limitOption", {}).get("name") != "LIMIT_OPTION_DEFAULT"):
        raise ValueError("unsupported SELECT shape")
    relations = root.get("fromClause", ())
    if len(relations) != 1:
        raise ValueError("one relation required")
    relation = relations[0]
    if (relation.get("@") != "RangeVar"
            or set(relation) - {"@", "schemaname", "relname", "inh", "relpersistence", "location"}):
        raise ValueError("unsupported relation")
    table = relation.get("schemaname", "") + "." + relation.get("relname", "")
    if table not in tables:
        raise ValueError("relation outside registry")

    def column(node):
        if node.get("@") != "ColumnRef" or set(node) - {"@", "fields", "location"}:
            raise ValueError("explicit column required")
        fields = node.get("fields", ())
        if len(fields) != 1 or fields[0].get("@") != "String":
            raise ValueError("unqualified explicit column required")
        name = fields[0].get("sval")
        if name not in tables[table]:
            raise ValueError("column outside registry")
        return name

    columns = []
    for target in root.get("targetList", ()):
        if target.get("@") != "ResTarget" or set(target) - {"@", "val", "location"}:
            raise ValueError("unsupported target")
        columns.append(column(target.get("val", {})))
    if not columns or len(columns) > 64:
        raise ValueError("invalid target count")
    predicate = root.get("whereClause", {})
    if (predicate.get("@") != "A_Expr"
            or set(predicate) - {"@", "kind", "name", "lexpr", "rexpr", "location",
                                  "rexpr_list_start", "rexpr_list_end"}
            or predicate.get("kind", {}).get("name") != "AEXPR_OP"):
        raise ValueError("single parameter comparison required")
    operators = predicate.get("name", ())
    if (len(operators) != 1 or operators[0].get("@") != "String"
            or operators[0].get("sval") not in {"=", "<>", "<", "<=", ">", ">="}):
        raise ValueError("unsupported comparison")
    predicate_column = column(predicate.get("lexpr", {}))
    parameter = predicate.get("rexpr", {})
    if (parameter.get("@") != "ParamRef" or parameter.get("number") != 1
            or set(parameter) - {"@", "number", "location"} or parameter_count != 1):
        raise ValueError("exactly one bound parameter required")
    return ValidatedSelect(sql, table, tuple(columns), parameter_count,
                           predicate_column, operators[0]["sval"])
