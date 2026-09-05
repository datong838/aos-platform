"""Legacy content consumers must never turn runtime Installation active into a grant."""


def legacy_content_predicate(alias: str) -> str:
    """Only fixed host query aliases; no request-controlled SQL identifiers.

    Return an observation column, not a WHERE filter: callers must preserve
    replacement/latest selection before refusing the selected runtime lock.
    This is an additional exclusion, not a signature or permission validator.
    """
    if alias not in {'l', 'bil', 'composition_lock'}:
        raise ValueError('unsupported trusted lock alias')
    payload = alias + '.lock_payload'
    return f"""(
        jsonb_typeof({payload}->'resolved')='array'
        AND jsonb_array_length(CASE WHEN jsonb_typeof({payload}->'resolved')='array'
            THEN {payload}->'resolved' ELSE '[]'::jsonb END)>0
        AND NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(CASE
                WHEN jsonb_typeof({payload}->'resolved')='array'
                THEN {payload}->'resolved' ELSE '[]'::jsonb END) AS selected(value)
            LEFT JOIN asset_bundle boundary_bundle
                ON boundary_bundle.publisher=selected.value->>'publisher'
                AND boundary_bundle.bundle_id=selected.value->>'id'
            LEFT JOIN asset_bundle_version boundary_version
                ON boundary_version.bundle_pk=boundary_bundle.bundle_pk
                AND boundary_version.version=selected.value->>'version'
            WHERE boundary_version.content_hash IS DISTINCT FROM selected.value->>'contentHash'
                OR boundary_version.version_pk IS NULL
                OR jsonb_typeof(boundary_version.manifest_json->'spec') IS DISTINCT FROM 'object'
                OR (boundary_version.manifest_json->'spec'->'runtime' IS NOT NULL
                    AND boundary_version.manifest_json->'spec'->'runtime'<>'null'::jsonb)
        )
    )"""
