"""Assembly only; explicit authority doubles, no database or IPC."""
from uuid import UUID
from types import SimpleNamespace
import pytest
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.tenant_scope import TenantScope


def test_factory_shares_source_owner_and_only_uses_saved_input(monkeypatch):
    scope=TenantScope('org-org','dev-project');selection=object.__new__(PipelineSourceSelectionOwner)
    factory=object.__new__(PipelineControlServiceFactory)
    object.__setattr__(factory,'installation_store',object());object.__setattr__(factory,'policy',object())
    calls=[]
    monkeypatch.setattr(PipelineControlServiceFactory,'_source_dependencies',lambda self,s:calls.append(s) or (selection,object()))
    monkeypatch.setattr(ProductEventControlQualifiedOwner,'__init__',lambda self,**kw:setattr(self,'_source',kw['selections']))
    def init(self,**kwargs):
        self.__dict__.update(kwargs)
    monkeypatch.setattr(CurrentInstalledPackageInvoker,'__init__',init)
    ref=dict(resourceType='PipelineRuntimeControlRevision',resourceId='pipeline-control-11111111-1111-4111-8111-111111111111',
        revision=1,contentHash='sha256:'+'a'*64)
    service=factory.build_event_consumer(scope,actor='fixture-actor',run_id='original-run',control_ref=ref,
        installation_id=UUID(int=1),generation=UUID(int=2),live_directory=object(),markings=('internal',),
        store=object.__new__(EcomConsistencyStore))
    assert calls==[scope]
    assert service.reader._owner is selection is service.control._owner._source
    journal=service.reader._journal
    assert journal._completed_read is True and journal._saved_recovery is False and journal._run_id=='original-run'
    assert journal._scope==scope and journal._actor=='fixture-actor'
    assert service.invoker.package_id=='domain.ecommerce.core'
    assert service.invoker.installation_store is factory.installation_store
    assert service.invoker.markings==('internal',)
