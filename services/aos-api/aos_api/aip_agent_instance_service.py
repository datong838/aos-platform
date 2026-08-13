"""Application service for tenant-customized AIP AgentInstance lifecycle."""
from aos_api.aip_agent_registry_store import AipAgentRegistryStore


class AipAgentInstanceService:
    def __init__(self, store: AipAgentRegistryStore | None = None) -> None:
        self.store = store or AipAgentRegistryStore()

    def create(self, *args, **kwargs):
        return self.store.create_instance(*args, **kwargs)

    def update(self, *args, **kwargs):
        return self.store.update_instance(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.store.get_instance(*args, **kwargs)

    def list(self, *args, **kwargs):
        return self.store.list_instances(*args, **kwargs)
