"""Idempotently publish AIP definitions from the ecommerce SolutionPack authority."""
from __future__ import annotations

import json
from pathlib import Path

from aos_api.aip_solution_pack_publisher import AipSolutionPackPublisher


def main() -> None:
    bundle_dir = Path(__file__).resolve().parents[3] / "bundles/solutions/ecommerce-growth"
    result = AipSolutionPackPublisher().publish(bundle_dir, actor="aip6-solution-pack-publisher")
    print(
        json.dumps(
            {
                "bundleId": result.bundle_id,
                "bundleVersion": result.bundle_version,
                "agentCount": result.agent_count,
                "skillCount": result.skill_count,
                "capabilityCount": result.capability_count,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
