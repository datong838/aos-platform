"""Explicit isolated fixture adaptation; original files and checks remain intact."""
import ast
import hashlib
import inspect
from pathlib import Path


def install(patch, evidence, occupation_module=None):
    from tests.aip import test_physical_capacity_occupation_pg as occupation
    from tests.aip import test_capacity_source_publication_transaction_pg as publication

    if occupation_module is not None:
        occupation = occupation_module
    def record_boundary(label):
        import json, datetime
        with (evidence / "auth-boundary-executed.jsonl").open("a") as out:
            out.write(json.dumps({"boundary": label, "at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "original_fields_preserved": True}) + "\n")

    specifications = [
        (occupation.test_source_model_preparation_original_native_caller,
         '        with psycopg.connect(**params, row_factory=dict_row) as caller:',
         "        from pydantic import SecretStr\n"
         "        fresh_command = command.model_copy(update={'bearer_token': SecretStr(sign(original[0]['maker']))})\n"
         "        assert fresh_command.model_dump(exclude={'bearer_token'}) == command.model_dump(exclude={'bearer_token'})\n"
         "        command = fresh_command\n"
         "        _record_auth_boundary('independent-consumer')\n"),
        (publication.native_original_fact_reader._get_wrapped_function(),
         '    with connect_capacity_issuer(config,SCOPE) as restored:',
         "    from pydantic import SecretStr\n"
         "    sign, _ = request.getfixturevalue('https_signer')\n"
         "    fresh_command = command.model_copy(update={'bearer_token': SecretStr(sign(f['maker']))})\n"
         "    assert fresh_command.model_dump(exclude={'bearer_token'}) == command.model_dump(exclude={'bearer_token'})\n"
         "    command = fresh_command\n"
         "    _record_auth_boundary('independent-teardown')\n"),
    ]
    bindings = []
    for function, anchor, addition in specifications:
        assert not function.__code__.co_freevars
        original = inspect.getsource(function)
        assert original.count(anchor) == 1
        modified = original.replace(anchor, addition + anchor)
        assert ast.dump(ast.parse(modified.replace(addition, '', 1))) == ast.dump(ast.parse(original))
        tree = ast.parse(modified)
        assert len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef)
        tree.body[0].decorator_list = []
        patch.setitem(function.__globals__, "_record_auth_boundary", record_boundary)
        namespace = dict(function.__globals__)
        path = evidence / (function.__name__ + '-fresh-auth.py')
        path.write_text(modified)
        exec(compile(tree, str(path), 'exec'), namespace)
        replacement = namespace[function.__name__]
        assert inspect.signature(replacement) == inspect.signature(function)
        patch.setattr(function, '__code__', replacement.__code__)
        bindings.append({'function': function.__name__,
                         'original_sha256': hashlib.sha256(original.encode()).hexdigest(),
                         'modified_sha256': hashlib.sha256(modified.encode()).hexdigest(),
                         'all_original_ast_preserved': True})
    return bindings
