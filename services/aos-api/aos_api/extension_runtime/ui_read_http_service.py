"""HTTP use cases own one restricted transaction; never start package workers."""
from .ui_read_admission import RuntimeUiReadAdmission
from .ui_read_query import RuntimeUiReadQuery
from .ui_read_connection import ui_read_connection


class RuntimeUiReadHttpService:
    def __init__(self, *, catalog_provider, connect=ui_read_connection):
        if not callable(catalog_provider) or not callable(connect):
            raise TypeError('trusted UI read dependencies required')
        self.catalog_provider = catalog_provider
        self.connect = connect

    def enqueue(self, *, scope, subject, markings, idempotency_key, request):
        service = RuntimeUiReadAdmission(catalog=self.catalog_provider())
        with self.connect(scope=scope, subject=subject) as conn:
            delivery = service.enqueue(conn=conn, scope=scope, subject=subject,
                required_markings=markings, idempotency_key=idempotency_key, request=request)
        return dict(schemaVersion='aos.runtime-ui-read-status/v1',
            tenant={'orgId': scope.org_id, 'projectId': scope.project_id},
            requestId=str(delivery.request_id), requestHash=delivery.request_hash,
            state=delivery.state, revision=delivery.revision, deadline=delivery.deadline.isoformat())

    def get(self, *, scope, subject, markings, request_id):
        service = RuntimeUiReadQuery(catalog=self.catalog_provider())
        with self.connect(scope=scope, subject=subject) as conn:
            value = service.get(conn=conn, scope=scope, subject=subject,
                required_markings=markings, request_id=request_id)
        return dict(schemaVersion='aos.runtime-ui-read-status/v1',
            tenant={'orgId': scope.org_id, 'projectId': scope.project_id}, **value)
