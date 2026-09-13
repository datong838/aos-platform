"""Request-scoped schedule dispatch; current authority remains transaction-owned."""
from collections.abc import Mapping

from aos_api.auth import Principal
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.tenant_scope import TenantScope


class EventAwareSchedulePutHostService:
    executor_identity = 'ecommerce-growth-schedule-host'

    def __init__(self, principal: Principal, factory: PipelineControlServiceFactory):
        if type(principal) is not Principal or type(factory) is not PipelineControlServiceFactory:
            raise TypeError('exact authenticated principal and pipeline factory required')
        if type(principal.subject) is not str or not 1 <= len(principal.subject) <= 240 or not principal.subject.isprintable() or not principal.subject.strip():
            raise ValueError('authenticated actor required')
        from aos_api.ecommerce_growth_runtime_adapters import SchedulePutHostService
        self._scope = TenantScope(principal.org_id, principal.project_id)
        self._actor = principal.subject
        self._factory = factory
        self._legacy = SchedulePutHostService()
        self._event = None

    def _select(self, scope, command):
        if type(scope) is not TenantScope or scope != self._scope:
            raise ValueError('request scope drifted')
        if not isinstance(command, Mapping):
            raise ValueError('command required')
        policy = command.get('policy')
        if not isinstance(policy, Mapping) or 'schemaVersion' not in policy:
            return self._legacy
        if policy['schemaVersion'] != 'aos.ecommerce.product-event-schedule-policy/v1':
            raise ValueError('unknown schedule policy schema')
        if self._event is None:
            from aos_api.ecommerce_product_event_host_service import ProductEventSchedulePutHostService
            self._event = ProductEventSchedulePutHostService(
                self._factory.build_event_owner(self._scope), actor=self._actor)
        return self._event

    def revalidate(self, *, scope, command, **kwargs):
        return self._select(scope, command).revalidate(scope=scope, command=command, **kwargs)

    def execute(self, *, scope, command, **kwargs):
        return self._select(scope, command).execute(scope=scope, command=command, **kwargs)

    def verify_receipt(self, *, scope, command, **kwargs):
        return self._select(scope, command).verify_receipt(scope=scope, command=command, **kwargs)
