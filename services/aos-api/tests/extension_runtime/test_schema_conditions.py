import json

import pytest

from test_admission import fixture


@pytest.mark.parametrize('case', ['valid','missing','unknown','duplicate','wrong_hash','empty_storage','empty_pure','tampered','duplicate_key'])
def test_schema_requirements_are_exact_signed_artifacts(case):
    from aos_api.extension_runtime.schema_conditions import admit_schema_requirements
    def files(items):
        doc={'schemaVersion':1,'requirements':[{'version':'1','migrationHash':'sha256:'+'e'*64}]}
        if case=='unknown':doc['extra']=True
        if case=='duplicate':doc['requirements']*=2
        if case=='wrong_hash':doc['requirements'][0]['migrationHash']='bad'
        if case in {'empty_storage','empty_pure'}:doc['requirements']=[]
        if case=='empty_pure':items.pop('artifacts/storage-registry.json')
        if case!='missing':items['artifacts/schema-requirements.json']=json.dumps(doc).encode()
        if case=='duplicate_key':items['artifacts/schema-requirements.json']=b'{"schemaVersion":1,"schemaVersion":1,"requirements":[]}'
    args,items=fixture(files)
    if case=='tampered':items['artifacts/schema-requirements.json']=b'{}'
    kwargs={key:args[key] for key in ('record','selected','policy','checked_at','read_artifact')}
    if case=='empty_pure':assert admit_schema_requirements(**kwargs)==()
    elif case=='valid':
        result=admit_schema_requirements(**kwargs)
        from aos_api.extension_runtime.schema_conditions import schema_package_id
        assert len(result)==1 and result[0].package_id==schema_package_id(args['selected'].publisher,args['selected'].id)
    else:
        with pytest.raises((ValueError,LookupError)):admit_schema_requirements(**kwargs)


def test_schema_identity_separates_publishers_and_preserves_bundle_identity():
    from aos_api.extension_runtime.schema_conditions import schema_package_id
    assert schema_package_id('publisher-a','example')!=schema_package_id('publisher-b','example')
    assert schema_package_id('publisher-a','example')==schema_package_id('publisher-a','example')
    args,_=fixture()
    first=args['selected']
    second=first.model_copy(update={'version':'2.0.0','content_hash':'sha256:'+'f'*64})
    assert schema_package_id(first.publisher,first.id)==schema_package_id(second.publisher,second.id)
