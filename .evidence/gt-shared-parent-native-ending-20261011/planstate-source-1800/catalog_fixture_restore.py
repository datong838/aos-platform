"""Fixed original-family restoration for the owned native fixture only."""
from aos_api import aip_provider_capacity_catalog_audit_profile as catalog
from aos_api import aip_provider_capacity_publication_store as store

def original_family_restoration_statements():
    epoch = catalog.epoch
    original_fact = epoch._body(store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL, catalog.FACT)
    return (*epoch.legacy_epoch_profile_restoration_statements(),
            epoch._definition(catalog.FACT, original_fact))
