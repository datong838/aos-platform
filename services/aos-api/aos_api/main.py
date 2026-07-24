"""AOS API application factory — Wave-0/1/2."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aos_api.db import init_schema, seed_if_empty
from aos_api.module_store import seed_modules_if_empty
from aos_api.errors import register_exception_handlers
from aos_api.logging_facade import configure_logging, get_logger
from aos_api.middleware import TraceLogMiddleware
from aos_api.routers import (
    actions,
    action_enhancements,
    action_finale,
    action_further,
    action_params,
    action_rules,
    action_visual_editor,
    action_webhook,
    aip_assist,
    aip_extras,
    aip_nodes,
    analytics,
    agent_health_migration_webhook,
    ssl_health_snooze_marketplace,
    linter_foundry_rules,
    gantt_ml_drag_pricing,
    autoscale_telemetry_volume_cop,
    tracing_perf_geo_map,
    vertex_geo_ts_process_hyperauto,
    auth_oidc,
    authz,
    buddy,
    builds,
    cap_and_markings,
    code_collaboration,
    column_impact,
    connection_cdc_schedule,
    compute_module,
    compute_module_extras,
    csv_ontology_export_action_metrics,
    compute_module_publish,
    data_connection_admin,
    data_connection_extras,
    data_connection_export,
    data_connection_webhook,
    data_connection_security,
    lineage_visualization,
    data_health,
    data_health_integration,
    data_health_plus,
    dataset_preview_health,
    data_transaction,
    decision_audit,
    dev_tooling,
    drafts,
    evals,
    expectation,
    file_processing,
    function_types,
    functions,
    functions_dev_tools,
    functions_runtime,
    funnel,
    funnel_mappings,
    gantt,
    health,
    incremental_sync,
    integration_maintenance,
    lineage,
    lineage_views,
    logic,
    logic_flows,
    llm_extras,
    llm_routing,
    llm_node_agent_proxy,
    l4_automation,
    me,
    media_references,
    media_set_browser_interaction,
    media_sets,
    metrics,
    modules,
    multi_language,
    multi_source,
    materialized_access_control,
    object_explorer,
    object_sets,
    object_storage_indexing,
    object_views,
    object_editing,
    oe_enhancements,
    oma_editor,
    ontology,
    ontology_data_layer,
    ontology_governance,
    ontology_management,
    ontology_outputs,
    ontology_roles,
    ops_local,
    orgs,
    ops_tenants,
    ops_ttl,
    ops_version_matrix,
    otp,
    pipelines,
    pipeline_outputs,
    pipeline_type_semantics,
    pipeline_builder_extra,
    pipeline_canvas_extras,
    pipeline_ui_components,
    plugins,
    platform_integrations,
    python_functions,
    runtime_write,
    scheduling,
    scheduling_rules_lint,
    shell_core,
    sql_console,
    tool_registry,
    type_system,
    transforms,
    triggers_and_link_output,
    timeseries_sap_functions,
    wave_ext,
    dicom_workshop_docintel,
    web_ide,
    workshop_compute_api,
    workspaces,
    writeback,
)

from aos_api import aip_langgraph_runtime_router as aip_langgraph_runtime_router
from aos_api import aip_propose_edits_router as aip_propose_edits_router
from aos_api import aip_wiki_field_router as aip_wiki_field_router
from aos_api import aip_logic_state_router as aip_logic_state_router
from aos_api import aip_logic_version_router as aip_logic_version_router
from aos_api import aip_debug_cot_router as aip_debug_cot_router
from aos_api import aip_debug_tools_router as aip_debug_tools_router
from aos_api import aip_eval_crud_router as aip_eval_crud_router
from aos_api import aip_eval_gate_router as aip_eval_gate_router
from aos_api import aip_eval_cross_model_router as aip_eval_cross_model_router
from aos_api import aip_eval_dashboard_router as aip_eval_dashboard_router
from aos_api import aip_eval_rag_router as aip_eval_rag_router
from aos_api import aip_eval_gen_router as aip_eval_gen_router
from aos_api import aip_eval_tool_router as aip_eval_tool_router
from aos_api import aip_l4_gate_router as aip_l4_gate_router
from aos_api import aip_l4_circuit_router as aip_l4_circuit_router
from aos_api import aip_app_state_router as aip_app_state_router
from aos_api import aip_rag_context_router as aip_rag_context_router
from aos_api import aip_long_memory_router as aip_long_memory_router
from aos_api import aip_trace_logic_router as aip_trace_logic_router
from aos_api import aip_metrics_router as aip_metrics_router
from aos_api import aip_obs_dashboard_router as aip_obs_dashboard_router
from aos_api import aip_alerts_router as aip_alerts_router
from aos_api import aip_model_catalog_router as aip_model_catalog_router
from aos_api import aip_model_capacity_router as aip_model_capacity_router
from aos_api import aip_model_lifecycle_router as aip_model_lifecycle_router
from aos_api import aip_assist_context_router as aip_assist_context_router
from aos_api import aip_assist_perms_router as aip_assist_perms_router
from aos_api import aip_analyst_chart_router as aip_analyst_chart_router
from aos_api import aip_analyst_explore_router as aip_analyst_explore_router
from aos_api import aip_docintel_parse_router as aip_docintel_parse_router
from aos_api import aip_docintel_extract_router as aip_docintel_extract_router
from aos_api import aip_docintel_semantic_router as aip_docintel_semantic_router

configure_logging()
log = get_logger("aos-api")

# Load aos-platform/.env (AGNES_* etc.) before request handlers run
try:
    from aos_api.env_load import load_dotenv

    loaded = load_dotenv()
    if loaded:
        log.info("dotenv_loaded path=%s", loaded)
except Exception:  # pragma: no cover
    log.exception("dotenv_load_failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        init_schema()
        seed_if_empty()
        try:
            seed_modules_if_empty()
        except Exception:
            log.exception("startup_module_store_failed_continue")
        try:
            from aos_api.tenant_catalog import boot_tenant_catalogs

            boot_tenant_catalogs()
        except Exception:
            log.exception("startup_tenant_catalog_failed_continue")
        try:
            from aos_api import data_os_store
            from aos_api.routers import wave_ext as wave_ext_mod

            data_os_store.boot_data_os(wave_ext_mod)
        except Exception:
            log.exception("startup_data_os_failed_continue")
        log.info("startup_meta_store_ok")
    except Exception:
        log.exception("startup_meta_store_failed_continue")
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="aos-api", version="0.3.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        # Web :5173 · 桌面 Tauri dev :1420 · 打包壳 tauri://
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:1420",
            "http://localhost:1420",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )
    application.add_middleware(TraceLogMiddleware)
    register_exception_handlers(application)
    application.include_router(health.router)
    application.include_router(metrics.router)
    application.include_router(auth_oidc.router)
    application.include_router(authz.router)
    application.include_router(me.router)
    application.include_router(otp.router)
    application.include_router(orgs.router)
    application.include_router(ops_tenants.router)
    application.include_router(ops_version_matrix.router)
    application.include_router(ops_local.router)
    application.include_router(ops_ttl.router)
    application.include_router(workspaces.router)
    application.include_router(buddy.router)
    application.include_router(modules.router)
    application.include_router(plugins.router)
    application.include_router(platform_integrations.router)
    application.include_router(object_sets.router)
    application.include_router(object_storage_indexing.router)
    application.include_router(ontology.router)
    application.include_router(ontology_governance.router)
    application.include_router(ontology_management.router)
    application.include_router(ontology_data_layer.router)
    application.include_router(oe_enhancements.router)
    application.include_router(object_editing.router)
    application.include_router(oma_editor.router)
    application.include_router(type_system.router)
    application.include_router(actions.router)
    application.include_router(drafts.router)
    application.include_router(gantt.router)
    application.include_router(runtime_write.router)
    application.include_router(analytics.router)
    application.include_router(agent_health_migration_webhook.router)
    application.include_router(ssl_health_snooze_marketplace.router)
    application.include_router(linter_foundry_rules.router)
    application.include_router(gantt_ml_drag_pricing.router)
    application.include_router(autoscale_telemetry_volume_cop.router)
    application.include_router(tracing_perf_geo_map.router)
    application.include_router(vertex_geo_ts_process_hyperauto.router)
    application.include_router(wave_ext.router)
    application.include_router(dicom_workshop_docintel.router)
    application.include_router(builds.router)
    application.include_router(shell_core.router)
    application.include_router(sql_console.router)
    application.include_router(writeback.router)
    application.include_router(data_transaction.router)
    application.include_router(expectation.router)
    application.include_router(action_enhancements.router)
    application.include_router(action_params.router)
    application.include_router(action_further.router)
    application.include_router(action_webhook.router)
    application.include_router(action_finale.router)
    application.include_router(llm_routing.router)
    application.include_router(llm_node_agent_proxy.router)
    application.include_router(llm_extras.router)
    application.include_router(lineage.router)
    application.include_router(lineage_views.router)
    application.include_router(pipelines.router)
    application.include_router(transforms.router)
    application.include_router(python_functions.router)
    application.include_router(functions.router)
    application.include_router(function_types.router)
    application.include_router(functions_dev_tools.router)
    application.include_router(funnel.router)
    application.include_router(funnel_mappings.router)
    application.include_router(ontology_roles.router)
    application.include_router(ontology_outputs.router)
    application.include_router(pipeline_outputs.router)
    application.include_router(pipeline_type_semantics.router)
    application.include_router(pipeline_builder_extra.router)
    application.include_router(pipeline_canvas_extras.router)
    application.include_router(pipeline_ui_components.router)
    application.include_router(triggers_and_link_output.router)
    application.include_router(code_collaboration.router)
    application.include_router(column_impact.router)
    application.include_router(connection_cdc_schedule.router)
    application.include_router(compute_module.router)
    application.include_router(compute_module_extras.router)
    application.include_router(csv_ontology_export_action_metrics.router)
    application.include_router(compute_module_publish.router)
    application.include_router(data_connection_admin.router)
    application.include_router(data_connection_extras.router)
    application.include_router(data_connection_export.router)
    application.include_router(data_connection_webhook.router)
    application.include_router(data_connection_security.router)
    application.include_router(lineage_visualization.router)
    application.include_router(data_health.router)
    application.include_router(data_health_plus.router)
    application.include_router(data_health_integration.router)
    application.include_router(dataset_preview_health.router)
    application.include_router(dev_tooling.router)
    application.include_router(media_references.router)
    application.include_router(media_set_browser_interaction.router)
    application.include_router(media_sets.router)
    application.include_router(logic.router)
    application.include_router(evals.router)
    application.include_router(file_processing.router)
    application.include_router(tool_registry.router)
    application.include_router(aip_nodes.router)
    application.include_router(aip_extras.router)
    application.include_router(aip_assist.router)
    application.include_router(logic_flows.router)
    application.include_router(l4_automation.router)
    application.include_router(decision_audit.router)
    application.include_router(cap_and_markings.router)
    application.include_router(multi_language.router)
    application.include_router(functions_runtime.router)
    application.include_router(object_views.router)
    application.include_router(object_explorer.router)
    application.include_router(action_rules.router)
    application.include_router(action_visual_editor.router)
    application.include_router(multi_source.router)
    application.include_router(materialized_access_control.router)
    application.include_router(incremental_sync.router)
    application.include_router(integration_maintenance.router)
    application.include_router(scheduling.router)
    application.include_router(scheduling_rules_lint.router)
    application.include_router(web_ide.router)
    application.include_router(workshop_compute_api.router)
    application.include_router(timeseries_sap_functions.router)
    application.include_router(aip_langgraph_runtime_router.router)
    application.include_router(aip_propose_edits_router.router)
    application.include_router(aip_wiki_field_router.router)
    application.include_router(aip_logic_state_router.router)
    application.include_router(aip_logic_version_router.router)
    application.include_router(aip_debug_cot_router.router)
    application.include_router(aip_debug_tools_router.router)
    application.include_router(aip_eval_crud_router.router)
    application.include_router(aip_eval_gate_router.router)
    application.include_router(aip_eval_cross_model_router.router)
    application.include_router(aip_eval_dashboard_router.router)
    application.include_router(aip_eval_rag_router.router)
    application.include_router(aip_eval_gen_router.router)
    application.include_router(aip_eval_tool_router.router)
    application.include_router(aip_l4_gate_router.router)
    application.include_router(aip_l4_circuit_router.router)
    application.include_router(aip_app_state_router.router)
    application.include_router(aip_rag_context_router.router)
    application.include_router(aip_long_memory_router.router)
    application.include_router(aip_trace_logic_router.router)
    application.include_router(aip_metrics_router.router)
    application.include_router(aip_obs_dashboard_router.router)
    application.include_router(aip_alerts_router.router)
    application.include_router(aip_model_catalog_router.router)
    application.include_router(aip_model_capacity_router.router)
    application.include_router(aip_model_lifecycle_router.router)
    application.include_router(aip_assist_context_router.router)
    application.include_router(aip_assist_perms_router.router)
    application.include_router(aip_analyst_chart_router.router)
    application.include_router(aip_analyst_explore_router.router)
    application.include_router(aip_docintel_parse_router.router)
    application.include_router(aip_docintel_extract_router.router)
    application.include_router(aip_docintel_semantic_router.router)
    log.info("aos-api_app_created version=%s", application.version)
    return application


app = create_app()
