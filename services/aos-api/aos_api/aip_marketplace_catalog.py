"""R18 marketplace projection over the versioned ecommerce SolutionPack."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
from aos_api.aip_marketplace_import_contracts import (
    MarketplaceAgentReadiness,
    MarketplaceCatalogResponse,
    MarketplacePackage,
)
from aos_api.aip_solution_pack_publisher import SOLUTION_PACK_ID, SOLUTION_PACK_VERSION
from aos_api.auth import Principal


def _bundle_root() -> Path:
    return Path(__file__).resolve().parents[3] / "bundles/solutions/ecommerce-growth"


def _bundle_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _repair(blockers: list[str]) -> tuple[str, str]:
    joined = " ".join(blockers)
    if any(word in joined for word in ("provider", "route", "health", "capacity", "price", "budget")):
        return "/aip/model-runtime", "检查模型运行就绪"
    if "eval" in joined:
        return "/aip/evals", "检查评测门控"
    if "production" in joined:
        return "/aip/production-contracts", "检查生产契约"
    if any(word in joined for word in ("capability", "skill", "binding")):
        return "/aip/agent-registry", "检查目录与绑定"
    return "/aip/agent-registry", "查看精确阻断"


class AipMarketplaceCatalog:
    def __init__(self, *, installer: AipEcommerceAgentInstaller | None = None, root: Path | None = None) -> None:
        self._installer = installer or AipEcommerceAgentInstaller()
        self._root = root or _bundle_root()

    def list(self, principal: Principal) -> MarketplaceCatalogResponse:
        manifest = yaml.safe_load((self._root / "bundle.yaml").read_text(encoding="utf-8"))
        agents_doc = json.loads((self._root / "content/agents/ecommerce-six-coworkers.json").read_text(encoding="utf-8"))
        logic_doc = json.loads((self._root / "content/logic/ecommerce-37-logic-catalog.json").read_text(encoding="utf-8"))
        capability_doc = json.loads((self._root / "content/agents/ecommerce-capability-catalog.json").read_text(encoding="utf-8"))
        catalog = self._installer.catalog(principal)
        readiness = []
        for item in catalog.items:
            href, label = _repair(item.blockers)
            readiness.append(
                MarketplaceAgentReadiness(
                    template_id=item.template.template_id,
                    display_name=item.template.display_name,
                    installed=item.instance is not None,
                    runtime_readiness=item.runtime_readiness,
                    blockers=item.blockers,
                    repair_href=href,
                    repair_label=label,
                )
            )
        metadata = manifest["metadata"]
        package = MarketplacePackage(
            package_id=metadata["id"],
            version=metadata["version"],
            content_hash=_bundle_hash(self._root),
            display_name=metadata["displayName"],
            publisher=metadata["publisher"],
            license=metadata["license"],
            source_ref=ResourceRef(
                resource_type="SolutionPack",
                resource_id=SOLUTION_PACK_ID,
                revision=SOLUTION_PACK_VERSION,
                authority="asset-registry",
            ),
            agent_count=len(agents_doc["agents"]),
            skill_count=len(logic_doc["logics"]),
            capability_count=len(capability_doc["capabilities"]),
            installed_count=catalog.stats.installed_count,
            runnable_count=catalog.stats.runnable_count,
            agents=readiness,
        )
        return MarketplaceCatalogResponse(
            tenant=TenantContext(org_id=principal.org_id, project_id=principal.project_id),
            items=[package],
            count=1,
        )


__all__ = ["AipMarketplaceCatalog"]
