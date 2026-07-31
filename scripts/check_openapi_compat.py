#!/usr/bin/env python3
"""Conservative backward-compatibility check for generated OpenAPI JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _resolve(document: dict[str, Any], value: Any) -> Any:
    seen: set[str] = set()
    while isinstance(value, dict) and isinstance(value.get("$ref"), str):
        ref = value["$ref"]
        if not ref.startswith("#/") or ref in seen:
            return value
        seen.add(ref)
        current: Any = document
        for raw in ref[2:].split("/"):
            current = current[raw.replace("~1", "/").replace("~0", "~")]
        value = current
    return value


class Report:
    def __init__(self) -> None:
        self.breaking: list[dict[str, str]] = []
        self.manual: list[dict[str, str]] = []

    def add(self, bucket: str, pointer: str, reason: str) -> None:
        getattr(self, bucket).append({"pointer": pointer, "reason": reason})


def _compare_schema(old_doc: dict[str, Any], new_doc: dict[str, Any], old: Any, new: Any, pointer: str, context: str, report: Report) -> None:
    old = _resolve(old_doc, old)
    new = _resolve(new_doc, new)
    if not isinstance(old, dict) or not isinstance(new, dict):
        if _canonical(old) != _canonical(new):
            report.add("manual", pointer, "schema representation changed")
        return
    for keyword in ("oneOf", "allOf", "anyOf", "discriminator"):
        if _canonical(old.get(keyword)) != _canonical(new.get(keyword)):
            report.add("manual", f"{pointer}/{keyword}", "complex schema composition changed")
    if old.get("type") != new.get("type"):
        report.add("breaking", f"{pointer}/type", "schema type changed")
    old_enum, new_enum = old.get("enum"), new.get("enum")
    if isinstance(old_enum, list) and isinstance(new_enum, list):
        removed = [value for value in old_enum if value not in new_enum]
        added = [value for value in new_enum if value not in old_enum]
        if removed:
            report.add("breaking", f"{pointer}/enum", "enum values removed")
        if added:
            report.add("manual", f"{pointer}/enum", "enum values added")
    old_properties = old.get("properties", {})
    new_properties = new.get("properties", {})
    if isinstance(old_properties, dict) and isinstance(new_properties, dict):
        for name in sorted(set(old_properties) - set(new_properties)):
            report.add("breaking", f"{pointer}/properties/{name}", f"{context} property removed")
        old_required = set(old.get("required", []))
        new_required = set(new.get("required", []))
        if context == "request":
            for name in sorted(new_required - old_required):
                report.add("breaking", f"{pointer}/required", "request property became required")
        else:
            for name in sorted(old_required - new_required):
                report.add("breaking", f"{pointer}/required", "response property is no longer guaranteed")
        for name in sorted(set(old_properties) & set(new_properties)):
            _compare_schema(old_doc, new_doc, old_properties[name], new_properties[name], f"{pointer}/properties/{name}", context, report)
    if "items" in old and "items" in new:
        _compare_schema(old_doc, new_doc, old["items"], new["items"], f"{pointer}/items", context, report)


def _parameters(document: dict[str, Any], path_item: dict[str, Any], operation: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in list(path_item.get("parameters", [])) + list(operation.get("parameters", [])):
        parameter = _resolve(document, raw)
        result[(parameter.get("in", ""), parameter.get("name", ""))] = parameter
    return result


def _security_tightened(old: Any, new: Any) -> bool:
    old = old or []
    new = new or []
    if not old:
        return bool(new)
    if not new:
        return False
    for old_option in old:
        old_schemes = set(old_option)
        matched = False
        for new_option in new:
            if set(new_option).issubset(old_schemes) and all(set(new_option[key]).issubset(set(old_option[key])) for key in new_option):
                matched = True
                break
        if not matched:
            return True
    return False


def compare(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    report = Report()
    old_paths, new_paths = old.get("paths", {}), new.get("paths", {})
    for path in sorted(set(old_paths) - set(new_paths)):
        report.add("breaking", f"/paths/{path}", "path removed")
    for path in sorted(set(old_paths) & set(new_paths)):
        old_item, new_item = old_paths[path], new_paths[path]
        old_methods = {method for method in old_item if method.lower() in HTTP_METHODS}
        new_methods = {method for method in new_item if method.lower() in HTTP_METHODS}
        for method in sorted(old_methods - new_methods):
            report.add("breaking", f"/paths/{path}/{method}", "method removed")
        for method in sorted(old_methods & new_methods):
            pointer = f"/paths/{path}/{method}"
            old_op, new_op = old_item[method], new_item[method]
            if old_op.get("operationId") != new_op.get("operationId"):
                report.add("breaking", f"{pointer}/operationId", "operationId changed")
            old_params = _parameters(old, old_item, old_op)
            new_params = _parameters(new, new_item, new_op)
            for key in sorted(set(old_params) - set(new_params)):
                report.add("breaking", f"{pointer}/parameters/{key[0]}:{key[1]}", "parameter removed or renamed")
            for key in sorted(set(new_params) - set(old_params)):
                if new_params[key].get("required"):
                    report.add("breaking", f"{pointer}/parameters/{key[0]}:{key[1]}", "required parameter added")
            for key in sorted(set(old_params) & set(new_params)):
                old_parameter, new_parameter = old_params[key], new_params[key]
                if not old_parameter.get("required") and new_parameter.get("required"):
                    report.add("breaking", f"{pointer}/parameters/{key[0]}:{key[1]}/required", "parameter became required")
                _compare_schema(old, new, old_parameter.get("schema", {}), new_parameter.get("schema", {}), f"{pointer}/parameters/{key[0]}:{key[1]}/schema", "request", report)
            old_body = _resolve(old, old_op.get("requestBody", {}))
            new_body = _resolve(new, new_op.get("requestBody", {}))
            if old_body or new_body:
                if old_body and not new_body:
                    report.add("breaking", f"{pointer}/requestBody", "accepted request body removed")
                elif not old_body and new_body.get("required"):
                    report.add("breaking", f"{pointer}/requestBody", "required request body added")
                elif old_body and new_body:
                    if not old_body.get("required") and new_body.get("required"):
                        report.add("breaking", f"{pointer}/requestBody/required", "request body became required")
                    old_content, new_content = old_body.get("content", {}), new_body.get("content", {})
                    for media_type in sorted(set(old_content) - set(new_content)):
                        report.add("breaking", f"{pointer}/requestBody/content/{media_type}", "accepted request media type removed")
                    for media_type in sorted(set(old_content) & set(new_content)):
                        _compare_schema(old, new, old_body["content"][media_type].get("schema", {}), new_body["content"][media_type].get("schema", {}), f"{pointer}/requestBody/content/{media_type}/schema", "request", report)
            old_responses, new_responses = old_op.get("responses", {}), new_op.get("responses", {})
            old_success = {code for code in old_responses if str(code).startswith("2")}
            for code in sorted(old_success - set(new_responses)):
                report.add("breaking", f"{pointer}/responses/{code}", "successful response removed")
            for code in sorted(set(old_responses) & set(new_responses)):
                old_response = _resolve(old, old_responses[code])
                new_response = _resolve(new, new_responses[code])
                old_content, new_content = old_response.get("content", {}), new_response.get("content", {})
                for media_type in sorted(set(old_content) - set(new_content)):
                    report.add("breaking", f"{pointer}/responses/{code}/content/{media_type}", "response media type removed")
                for media_type in sorted(set(old_content) & set(new_content)):
                    _compare_schema(old, new, old_response["content"][media_type].get("schema", {}), new_response["content"][media_type].get("schema", {}), f"{pointer}/responses/{code}/content/{media_type}/schema", "response", report)
            if _security_tightened(old_op.get("security", old.get("security")), new_op.get("security", new.get("security"))):
                report.add("breaking", f"{pointer}/security", "security requirements tightened")
    verdict = "breaking" if report.breaking else "manual_review" if report.manual else "compatible"
    return {"verdict": verdict, "breaking": report.breaking, "manualReview": report.manual}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        old = json.loads(args.baseline.read_text(encoding="utf-8"))
        new = json.loads(args.candidate.read_text(encoding="utf-8"))
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise ValueError("OpenAPI roots must be JSON objects")
        if not isinstance(old.get("paths"), dict) or not isinstance(new.get("paths"), dict):
            raise ValueError("OpenAPI roots must contain a paths object")
        result = compare(old, new)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"verdict": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["verdict"] == "compatible" else 1


if __name__ == "__main__":
    raise SystemExit(main())
