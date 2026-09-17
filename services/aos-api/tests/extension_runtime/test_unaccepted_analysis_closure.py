from uuid import uuid4
import pytest
from aos_api.ecommerce_unaccepted_analysis_closure import (
    UnacceptedAnalysisClosureRequest,
    UnacceptedScheduleAnalysisClosureRequest,
)


def request():
    return dict(schemaVersion='aos.ecommerce.unaccepted-analysis-closure/v1',occurrenceId=str(uuid4()),
        fenceReceiptId=str(uuid4()),fenceContentHash='sha256:'+'a'*64,idempotencyKey='close-1')


@pytest.mark.parametrize('field,value',[('occurrenceId','bad'),('fenceReceiptId',''),('idempotencyKey',' close'),
    ('idempotencyKey','close\n'),('fenceContentHash','sha256:abcd'),('schemaVersion','unknown'),('accepted',True)])
def test_request_rejects_nonexact_input(field,value):
    with pytest.raises(ValueError):UnacceptedAnalysisClosureRequest.model_validate({**request(),field:value})


def test_exact_wire_roundtrip():
    wire=request()
    assert UnacceptedAnalysisClosureRequest.model_validate(wire).model_dump(mode='json',by_alias=True)==wire


def schedule_request():
    return dict(
        schemaVersion='aos.ecommerce.unaccepted-schedule-analysis-closure/v1',
        occurrenceId=str(uuid4()), scheduleControlReceiptId=str(uuid4()),
        scheduleControlContentHash='sha256:'+'b'*64, idempotencyKey='close-schedule-1',
    )


@pytest.mark.parametrize('field,value',[
    ('occurrenceId','bad'),('scheduleControlReceiptId',''),('idempotencyKey',' close'),
    ('scheduleControlContentHash','sha256:abcd'),('schemaVersion','unknown'),('accepted',True),
])
def test_schedule_request_rejects_nonexact_input(field,value):
    with pytest.raises(ValueError):
        UnacceptedScheduleAnalysisClosureRequest.model_validate({**schedule_request(),field:value})


def test_exact_schedule_wire_roundtrip():
    wire=schedule_request()
    assert UnacceptedScheduleAnalysisClosureRequest.model_validate(wire).model_dump(
        mode='json',by_alias=True)==wire
