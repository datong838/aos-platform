import pytest

from aos_api.ecommerce_released_event_control import ReleasedEventTarget


def test_released_event_target_is_exact_and_immutable():
    value=ReleasedEventTarget(
        installation_id='19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3',
        generation='64742c68-5e71-485b-a3c8-edc20be3d101',execution_epoch=3,
        runtime_revision=7,cutover_group_id='6a402d31-83ad-546c-807f-508c87498ce1',
        cutover_group_revision=37)
    assert value.execution_epoch==3
    with pytest.raises(Exception):
        value.execution_epoch=4


@pytest.mark.parametrize('field,value',[
    ('installation_id','not-a-uuid'),('execution_epoch',0),('runtime_revision',True)])
def test_released_event_target_rejects_ambiguous_identity(field,value):
    payload=dict(installation_id='19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3',
        generation='64742c68-5e71-485b-a3c8-edc20be3d101',execution_epoch=3,
        runtime_revision=7,cutover_group_id='6a402d31-83ad-546c-807f-508c87498ce1',
        cutover_group_revision=37)
    payload[field]=value
    with pytest.raises((TypeError,ValueError)):
        ReleasedEventTarget(**payload)
