import json
import logging

from aos_api.logging_facade import (
    JsonFormatter,
    configure_logging,
    get_logger,
    set_context,
)


def test_json_log_contains_trace_and_service():
    configure_logging()
    set_context(trace_id="tid-99", org_id="o1", project_id="p1")
    logger = get_logger("aos-api.test")
    record = logger.makeRecord(
        "aos-api.test",
        logging.INFO,
        __file__,
        1,
        "hello",
        (),
        None,
    )
    line = JsonFormatter().format(record)
    payload = json.loads(line)
    assert payload["service"] == "aos-api"
    assert payload["trace_id"] == "tid-99"
    assert payload["org_id"] == "o1"
    assert payload["msg"] == "hello"
