"""Reserved identity for a source-specific Owner approval and issuer command.

The identity grants no license and registers no metadata. Generic executors may
never consume its approval; a dedicated typed producer and issuer are required.
"""
SOURCE_LICENSE_ISSUANCE_ACTION = "aip_issue_source_license"


def is_source_license_action(action_type_id: str, snapshot: dict) -> bool:
    return SOURCE_LICENSE_ISSUANCE_ACTION in {action_type_id, snapshot.get("id")}
