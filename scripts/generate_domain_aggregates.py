#!/usr/bin/env python3
"""Generate domain_aggregates.py from main.py router imports.

Parses main.py to extract all router variable names, categorizes them into
10 domains by prefix, and writes the complete domain_aggregates.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parent.parent / "services" / "aos-api" / "aos_api" / "main.py"
OUTPUT = Path(__file__).resolve().parent.parent / "services" / "aos-api" / "aos_api" / "routers" / "domain_aggregates.py"


# ── Domain prefix mapping ──
# Priority order: more specific prefixes first
DOMAIN_PREFIXES = {
    # Ontology: object types, ontology editing, ontology config, ontology explorer
    "ontology": "ontology",
    "ontology_governance": "ontology",
    "ontology_management": "ontology",
    "ontology_data_layer": "ontology",
    "ontology_roles": "ontology",
    "ontology_outputs": "ontology",
    "oe_": "ontology",        # object editing enhancements
    "object_": "ontology",     # object_editing, object_sets, object_storage_indexing, object_views, object_explorer
    "oma_": "ontology",        # ontology management admin
    "type_system": "ontology",
    "funnel": "ontology",
    "funnel_mappings": "ontology",
    "multi_language": "ontology",
    "multi_source": "ontology",
    "materialized_access_control": "ontology",
    "incremental_sync": "ontology",
    "csv_ontology_export_action_metrics": "ontology",
    "ob_": "ontology",        # object browser
    "oc_": "ontology",        # ontology config
    "zz_": "ontology",        # property/function editors (misc ontology tools)
    "if_": "ontology",        # interface metadata (ontology-related)

    # Workshop: actions, modules, scheduling, compute, media, dev tooling
    "modules": "workshop",
    "workshop_": "workshop",
    "gantt": "workshop",
    "compute_module": "workshop",
    "drafts": "workshop",
    "dev_tooling": "workshop",
    "web_ide": "workshop",
    "integration_maintenance": "workshop",
    "scheduling": "workshop",
    "scheduling_rules_lint": "workshop",
    "actions": "workshop",
    "action_": "workshop",
    "media_": "workshop",
    "pp_": "workshop",        # pipeline presentation / toolbar
    "ds_": "workshop",        # dataset shell / context menu (not Data domain)
    "af_": "workshop",        # action forms
    "at_": "workshop",        # action types
    "ms_": "workshop",        # media sets
    "wk_": "workshop",        # workshop widgets
    "rl_": "workshop",        # rules
    "sc_": "workshop",        # scheduling
    "ca_": "workshop",        # capabilities (heavy capability, platform facade)

    # AIP: decision engine, logic, LLM, evals, tools
    "aip_": "aip",
    "logic": "aip",
    "logic_flows": "aip",
    "tool_registry": "aip",
    "evals": "aip",
    "file_processing": "aip",
    "decision_audit": "aip",
    "l4_automation": "aip",
    "llm_": "aip",
    "model_provider_": "aip",
    "provider_": "aip",
    "model_router_config": "aip",
    "module_events": "aip",
    "phase3_": "aip",
    "phase4_": "ontology",    # Phase 4 is ontology digital twin
    "phase5_": "data",        # Phase 5 is pipeline core
    "phase6_": "data",        # Phase 6 is data source/sync (but agents = agent domain)

    # Data: pipelines, transforms, connections, lineage, builds
    "builds": "data",
    "data_connection_": "data",
    "data_health": "data",
    "data_health_plus": "data",
    "data_health_integration": "data",
    "dataset_preview_health": "data",
    "data_transaction": "data",
    "lineage": "data",
    "lineage_views": "data",
    "lineage_visualization": "data",
    "pipelines": "data",
    "pipeline_": "data",
    "transforms": "data",
    "python_functions": "data",
    "functions": "data",
    "function_types": "data",
    "functions_dev_tools": "data",
    "functions_runtime": "data",
    "triggers_and_link_output": "data",
    "code_collaboration": "data",
    "column_impact": "data",
    "connection_cdc_schedule": "data",
    "shell_core": "data",
    "sql_console": "data",
    "writeback": "data",
    "expectation": "data",
    "timeseries_sap_functions": "data",
    "dc_": "data",           # data connection
    "di_": "data",           # data integration
    "dh_": "data",           # data health
    "dl_": "data",           # data lineage
    "pb_": "data",           # pipeline builder
    "cr_": "data",           # code repository
    "bd_": "data",           # build diagnostics
    "mt_": "data",           # transforms (meta-transform)
    "fn_": "data",           # functions
    "id_": "data",           # IDE dev tooling (mapped to Data/Infra based on content)

    # Model: geospatial, digital twin, ML
    "gantt_ml_drag_pricing": "model",
    "gs_": "model",          # geospatial
    "phase2_": "model",      # Phase 2 model management

    # Admin: orgs, tenants, workspaces, auth
    "orgs": "admin",
    "workspaces": "admin",
    "auth": "admin",
    "authz": "admin",
    "ops_tenants": "admin",
    "ops_ttl": "admin",
    "cap_and_markings": "admin",
    "au_": "admin",          # auth utilities

    # Infrastructure: health, metrics, plugins, runtime
    "health": "infra",
    "metrics": "infra",
    "runtime_write": "infra",
    "analytics": "infra",
    "plugins": "infra",
    "platform_integrations": "infra",
    "wave_ext": "aip",
    "dicom_workshop_docintel": "infra",
    "ssl_health_snooze_marketplace": "infra",
    "linter_foundry_rules": "infra",
    "autoscale_telemetry_volume_cop": "infra",
    "tracing_perf_geo_map": "infra",
    "vertex_geo_ts_process_hyperauto": "infra",
    "vs_": "infra",         # versioning / events system
    "es_": "infra",         # external system integrations

    # Agent: buddy, agent health
    "buddy": "agent",
    "agent_": "agent",
    "phase6_agents": "agent",  # override

    # System: me, otp, ops
    "me": "system",
    "otp": "system",
    "ops_": "system",

    # Apollo: hub/spoke/ferry
    "phase7_": "apollo",
    "cp_": "apollo",         # cross-platform
    "hs_": "apollo",         # hub/spoke
    "fr2_": "apollo",        # ferry
}


def categorize(name: str) -> str:
    """Map a router variable name to its domain."""
    for prefix, domain in sorted(DOMAIN_PREFIXES.items(), key=lambda x: -len(x[0])):
        if name.startswith(prefix):
            return domain
    print(f"  WARNING: uncategorized router: {name}", file=sys.stderr)
    return "infra"  # default fallback


def parse_main_py() -> dict[str, list[str]]:
    """Parse main.py and return domain -> [router_names] mapping."""
    text = MAIN_PY.read_text()

    # Find all include_router calls and extract the variable name
    # Pattern: application.include_router(xxx) or application.include_router(xxx.router)
    router_calls = re.findall(
        r'application\.include_router\((\w+(?:\.\w+)?)\)',
        text,
    )

    domains: dict[str, list[str]] = {d: [] for d in [
        "ontology", "workshop", "aip", "data", "model",
        "admin", "infra", "agent", "system", "apollo",
    ]}

    for call in router_calls:
        # Extract the base variable name (strip .router suffix)
        base = call.replace(".router", "")
        domain = categorize(base)
        domains[domain].append(base)

    return domains


def generate_domain_router(domain: str, router_names: list[str], main_text: str) -> str:
    """Generate a single domain router factory function."""
    tag_map = {
        "ontology": "Ontology",
        "workshop": "Workshop",
        "aip": "AIP",
        "data": "Data",
        "model": "Model",
        "admin": "Admin",
        "infra": "Infra",
        "agent": "Agent",
        "system": "System",
        "apollo": "Apollo",
    }
    func_map = {
        "ontology": "create_ontology_router",
        "workshop": "create_workshop_router",
        "aip": "create_aip_router",
        "data": "create_data_router",
        "model": "create_model_router",
        "admin": "create_admin_router",
        "infra": "create_infra_router",
        "agent": "create_agent_router",
        "system": "create_system_router",
        "apollo": "create_apollo_router",
    }

    # Separate routers by import pattern
    # Pattern A: from aos_api.routers import xxx → xxx.router
    # Pattern B1: from aos_api import xxx → xxx.router (AIP routers)
    # Pattern B2: from aos_api.xxx_router import router as xxx_router → xxx_router
    # Pattern B3: from aos_api.routers.xxx import router as xxx_router → xxx_router

    # We determine pattern by checking the main.py text
    text = main_text

    pattern_a = []  # from aos_api.routers import xxx → xxx.router
    pattern_b = []  # import router as xxx_router → xxx_router (no .router)

    for name in router_names:
        # Check if it's imported via "from aos_api.routers import xxx"
        if re.search(rf'from aos_api\.routers import [^)]*\b{name}\b', text):
            pattern_a.append(name)
        else:
            pattern_b.append(name)

    count = len(router_names)
    tag = tag_map[domain]
    func_name = func_map[domain]

    lines = []
    lines.append(f"def {func_name}() -> APIRouter:")
    lines.append(f'    """{tag} domain: {count} routers."""')
    lines.append(f'    r = APIRouter(prefix="", tags=["{tag}"])')
    lines.append("")

    if pattern_a:
        # Group into manageable import chunks (max 15 per import)
        chunk_size = 15
        lines.append("    # -- from aos_api.routers import xxx --")
        for i in range(0, len(pattern_a), chunk_size):
            chunk = pattern_a[i:i+chunk_size]
            lines.append("    from aos_api.routers import (")
            for name in chunk:
                lines.append(f"        {name},")
            lines.append("    )")

        lines.append("    for m in [")
        for i in range(0, len(pattern_a), 8):
            chunk = pattern_a[i:i+8]
            lines.append("        " + ", ".join(chunk) + ",")
        lines.append("    ]:")
        lines.append("        r.include_router(m.router)")
        lines.append("")

    if pattern_b:
        # For pattern B routers, we need to determine the exact import path
        # Most W4 routers: from aos_api.xxx_router import router as xxx_router
        # AIP routers: from aos_api import aip_xxx_router as aip_xxx_router
        # Phase routers: from aos_api.routers.xxx import router as xxx_router

        # Let's split pattern_b further based on the actual imports in main.py
        w4_routers = []
        aip_routers = []
        phase_routers = []
        phase6_agent_routers = []

        for name in pattern_b:
            if name.startswith("phase6_agents"):
                phase6_agent_routers.append(name)
            elif name.startswith("phase"):
                phase_routers.append(name)
            elif re.search(rf'from aos_api\.routers\.\w+ import router as {name}\b', text):
                phase_routers.append(name)
            elif re.search(rf'from aos_api import \w+ as {name}\b', text):
                aip_routers.append(name)
            else:
                w4_routers.append(name)

        # W4 routers: from aos_api.xxx_router import router as xxx_router
        if w4_routers:
            lines.append("    # -- W4 routers (from aos_api.xxx_router import router as ...) --")
            for name in w4_routers:
                lines.append(f"    from aos_api.{name} import router as {name}")
            lines.append("    for m in [")
            for i in range(0, len(w4_routers), 8):
                chunk = w4_routers[i:i+8]
                lines.append("        " + ", ".join(chunk) + ",")
            lines.append("    ]:")
            lines.append("        r.include_router(m)")  # no .router
            lines.append("")

        # AIP routers: from aos_api import xxx as xxx → .router
        if aip_routers:
            lines.append("    # -- AIP routers (from aos_api import xxx → .router) --")
            for name in aip_routers:
                lines.append(f"    from aos_api import {name}")
            lines.append("    for m in [")
            for i in range(0, len(aip_routers), 8):
                chunk = aip_routers[i:i+8]
                lines.append("        " + ", ".join(chunk) + ",")
            lines.append("    ]:")
            lines.append("        r.include_router(m.router)")
            lines.append("")

        # Phase routers: from aos_api.routers.xxx import router as xxx_router
        if phase_routers:
            lines.append("    # -- Phase routers (from aos_api.routers.xxx import router as ...) --")
            for name in phase_routers:
                # Try to find exact import line in main.py
                pat = rf"from (aos_api\.routers\.\w+) import router as {name}\b"
                m = re.search(pat, main_text)
                if m:
                    mod_path = m.group(1)
                    lines.append(f"    from {mod_path} import router as {name}")
                else:
                    print(f"  WARNING: could not find phase import for {name}", file=sys.stderr)
                    mod_path = name.replace("_router", "")
                    lines.append(f"    from aos_api.routers.{mod_path} import router as {name}")
            lines.append("    for m in [")
            for i in range(0, len(phase_routers), 8):
                chunk = phase_routers[i:i+8]
                lines.append("        " + ", ".join(chunk) + ",")
            lines.append("    ]:")
            lines.append("        r.include_router(m)")
            lines.append("")

        # Phase 6 agents router — special, needs .router access
        if phase6_agent_routers:
            lines.append("    # -- Phase 6 agents (from aos_api.routers.phase6_agents import router as ...) --")
            for name in phase6_agent_routers:
                mod_path = name.replace("_router", "")
                lines.append(f"    from aos_api.routers.{mod_path} import router as {name}")
            for name in phase6_agent_routers:
                lines.append(f"    r.include_router({name})")
            lines.append("")

    lines.append("    return r")
    return "\n".join(lines)


def main() -> None:
    print("Parsing main.py router includes...")
    # Always read from git HEAD to get original router list
    import subprocess
    result = subprocess.run(
        ["git", "show", "HEAD:services/aos-api/aos_api/main.py"],
        capture_output=True, text=True, cwd=str(MAIN_PY.parent.parent.parent)
    )
    main_text = result.stdout
    if not main_text:
        print("ERROR: Could not read main.py from git", file=sys.stderr)
        sys.exit(1)

    # Parse include_router calls from git version
    router_calls = re.findall(
        r'application\.include_router\((\w+(?:\.\w+)?)\)',
        main_text,
    )
    domains = {d: [] for d in [
        "ontology", "workshop", "aip", "data", "model",
        "admin", "infra", "agent", "system", "apollo",
    ]}
    for call in router_calls:
        base = call.replace(".router", "")
        domain = categorize(base)
        domains[domain].append(base)

    for domain, routers in domains.items():
        print(f"  {domain}: {len(routers)} routers")

    total = sum(len(r) for r in domains.values())
    print(f"  TOTAL: {total} routers")

    # Generate the file
    header = '''"""Domain router aggregates — group all routers into 10 domain-level APIRouters.

Auto-generated by scripts/generate_domain_aggregates.py.
DO NOT EDIT MANUALLY — edit the generator script instead.
"""
from __future__ import annotations

from fastapi import APIRouter


'''

    body_parts = []
    for domain in ["ontology", "workshop", "aip", "data", "model",
                   "admin", "infra", "agent", "system", "apollo"]:
        body_parts.append(generate_domain_router(domain, domains.get(domain, []), main_text))

    # Domain registry
    registry_lines = [
        "",
        "# ── Domain registry ──",
        "DOMAIN_ROUTERS = {",
    ]
    for domain in ["ontology", "workshop", "aip", "data", "model",
                   "admin", "infra", "agent", "system", "apollo"]:
        func_name = f"create_{domain}_router"
        registry_lines.append(f'    "{domain}": {func_name},')
    registry_lines.append("}")

    output = header + "\n\n".join(body_parts) + "\n".join(registry_lines) + "\n"
    OUTPUT.write_text(output)
    print(f"\nWritten: {OUTPUT}")
    print(f"File size: {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
