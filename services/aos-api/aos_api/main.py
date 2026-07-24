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
    dc_completion_strategy,
    dc_stream_mgmt,
    dc_erp_crm,
    di_view_lineage,
    di_task_debug,
    dl_build_strategy,
    dl_build_preview,
    dl_dep_order,
    dl_stale_diagnosis,
    ds_context_menu,
    pp_toolbar_settings,
    pb_build_vs_deploy,
    pb_build_profiles,
    pb_task_groups,
    pb_health_checks,
    cr_branch_menu,
    cr_pipeline_review,
    ms_header_extractor,
    ob_index_debug,
    es_sap_stream,
    id_py_transform_preview,
    id_build_panel,
    id_build_status,
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

# ── W4 imports (123 modules) ──
from aos_api.af_action_types_router import router as af_action_types_router
from aos_api.af_capabilities_router import router as af_capabilities_router
from aos_api.af_edit_counter_router import router as af_edit_counter_router
from aos_api.af_edited_marker_router import router as af_edited_marker_router
from aos_api.af_oma_editor_router import router as af_oma_editor_router
from aos_api.af_param_help_router import router as af_param_help_router
from aos_api.at_action_apply_perm_router import router as at_action_apply_perm_router
from aos_api.at_edit_only_mode_router import router as at_edit_only_mode_router
from aos_api.at_marketplace_types_router import router as at_marketplace_types_router
from aos_api.at_notification_link_router import router as at_notification_link_router
from aos_api.at_notification_permission_router import router as at_notification_permission_router
from aos_api.at_side_effect_perm_router import router as at_side_effect_perm_router
from aos_api.bd_dep_task_abort_router import router as bd_dep_task_abort_router
from aos_api.bd_force_build_router import router as bd_force_build_router
from aos_api.bd_freshness_router import router as bd_freshness_router
from aos_api.cr_build_affected_router import router as cr_build_affected_router
from aos_api.cr_default_branch_router import router as cr_default_branch_router
from aos_api.cr_fallback_branch_router import router as cr_fallback_branch_router
from aos_api.cr_impact_analysis_router import router as cr_impact_analysis_router
from aos_api.dc_agent_yaml_router import router as dc_agent_yaml_router
from aos_api.dc_app_state_router import router as dc_app_state_router
from aos_api.dc_curl_import_router import router as dc_curl_import_router
from aos_api.dc_export_tasks_router import router as dc_export_tasks_router
from aos_api.dc_stream_preview_router import router as dc_stream_preview_router
from aos_api.dc_sync_troubleshoot_router import router as dc_sync_troubleshoot_router
from aos_api.dc_test_connection_router import router as dc_test_connection_router
from aos_api.dc_webhook_source_router import router as dc_webhook_source_router
from aos_api.di_auto_dedup_router import router as di_auto_dedup_router
from aos_api.di_auto_register_router import router as di_auto_register_router
from aos_api.di_compression_toggle_router import router as di_compression_toggle_router
from aos_api.di_consistency_guarantee_router import router as di_consistency_guarantee_router
from aos_api.di_data_consistency_router import router as di_data_consistency_router
from aos_api.di_dataset_branch_router import router as di_dataset_branch_router
from aos_api.di_db_schema_table_router import router as di_db_schema_table_router
from aos_api.di_export_config_router import router as di_export_config_router
from aos_api.di_external_access_router import router as di_external_access_router
from aos_api.di_external_transforms_router import router as di_external_transforms_router
from aos_api.di_force_build_router import router as di_force_build_router
from aos_api.di_freshness_detect_router import router as di_freshness_detect_router
from aos_api.di_hot_cold_storage_router import router as di_hot_cold_storage_router
from aos_api.di_key_by_router import router as di_key_by_router
from aos_api.di_latency_sampling_router import router as di_latency_sampling_router
from aos_api.di_live_archive_router import router as di_live_archive_router
from aos_api.di_logic_change_trigger_router import router as di_logic_change_trigger_router
from aos_api.di_output_path_router import router as di_output_path_router
from aos_api.di_partition_control_router import router as di_partition_control_router
from aos_api.di_permission_roles_router import router as di_permission_roles_router
from aos_api.di_primary_key_config_router import router as di_primary_key_config_router
from aos_api.di_reset_stream_router import router as di_reset_stream_router
from aos_api.di_s3_api_router import router as di_s3_api_router
from aos_api.di_source_based_transform_router import router as di_source_based_transform_router
from aos_api.di_spark_engine_router import router as di_spark_engine_router
from aos_api.di_stream_schema_router import router as di_stream_schema_router
from aos_api.di_streaming_latency_router import router as di_streaming_latency_router
from aos_api.di_text_extraction_router import router as di_text_extraction_router
from aos_api.di_third_party_access_router import router as di_third_party_access_router
from aos_api.di_transforms_external_router import router as di_transforms_external_router
from aos_api.di_view_creation_router import router as di_view_creation_router
from aos_api.di_virtual_storage_router import router as di_virtual_storage_router
from aos_api.di_virtual_table_router import router as di_virtual_table_router
from aos_api.dl_branch_aware_router import router as dl_branch_aware_router
from aos_api.dl_chart_tools_router import router as dl_chart_tools_router
from aos_api.dl_dataset_preview_300_router import router as dl_dataset_preview_300_router
from aos_api.dl_faq_troubleshoot_router import router as dl_faq_troubleshoot_router
from aos_api.dl_flow_animation_router import router as dl_flow_animation_router
from aos_api.dl_node_indicators_router import router as dl_node_indicators_router
from aos_api.dl_permission_coloring_router import router as dl_permission_coloring_router
from aos_api.dl_permission_simulation_router import router as dl_permission_simulation_router
from aos_api.dl_plan_management_router import router as dl_plan_management_router
from aos_api.dl_property_histogram_router import router as dl_property_histogram_router
from aos_api.dl_related_artifacts_router import router as dl_related_artifacts_router
from aos_api.dl_share_permission_router import router as dl_share_permission_router
from aos_api.dl_stale_coloring_router import router as dl_stale_coloring_router
from aos_api.dl_svg_export_router import router as dl_svg_export_router
from aos_api.dl_user_permission_view_router import router as dl_user_permission_view_router
from aos_api.ds_backtick_search_router import router as ds_backtick_search_router
from aos_api.ds_inline_upload_router import router as ds_inline_upload_router
from aos_api.fn_pipeline_status_router import router as fn_pipeline_status_router
from aos_api.id_feature_matrix_router import router as id_feature_matrix_router
from aos_api.id_osdk_react_router import router as id_osdk_react_router
from aos_api.ms_create_pipeline_menu_router import router as ms_create_pipeline_menu_router
from aos_api.ms_file_add_router import router as ms_file_add_router
from aos_api.ob_agg_precision_router import router as ob_agg_precision_router
from aos_api.ob_monitor_notify_router import router as ob_monitor_notify_router
from aos_api.ob_stream_permission_router import router as ob_stream_permission_router
from aos_api.oc_destructive_confirm_router import router as oc_destructive_confirm_router
from aos_api.oc_global_search_router import router as oc_global_search_router
from aos_api.oc_metric_toggle_router import router as oc_metric_toggle_router
from aos_api.oc_org_level_toggle_router import router as oc_org_level_toggle_router
from aos_api.oc_permission_migration_router import router as oc_permission_migration_router
from aos_api.oc_sidebar_filter_router import router as oc_sidebar_filter_router
from aos_api.oe_admin_config_router import router as oe_admin_config_router
from aos_api.oe_app_sidebar_router import router as oe_app_sidebar_router
from aos_api.oe_column_config_router import router as oe_column_config_router
from aos_api.pb_add_data_modes_router import router as pb_add_data_modes_router
from aos_api.pb_ai_functions_router import router as pb_ai_functions_router
from aos_api.pb_branch_activity_router import router as pb_branch_activity_router
from aos_api.pb_branch_version_router import router as pb_branch_version_router
from aos_api.pb_color_groups_router import router as pb_color_groups_router
from aos_api.pb_data_expectations_router import router as pb_data_expectations_router
from aos_api.pb_detail_sidebar_router import router as pb_detail_sidebar_router
from aos_api.pb_export_java_router import router as pb_export_java_router
from aos_api.pb_fp_growth_router import router as pb_fp_growth_router
from aos_api.pb_history_records_router import router as pb_history_records_router
from aos_api.pb_marketplace_pkg_router import router as pb_marketplace_pkg_router
from aos_api.pb_override_dataset_router import router as pb_override_dataset_router
from aos_api.pb_param_system_router import router as pb_param_system_router
from aos_api.pb_show_hide_nodes_router import router as pb_show_hide_nodes_router
from aos_api.pb_snapshot_incremental_router import router as pb_snapshot_incremental_router
from aos_api.pb_structured_semi_router import router as pb_structured_semi_router
from aos_api.pb_transform_library_router import router as pb_transform_library_router
from aos_api.pb_unit_test_router import router as pb_unit_test_router
from aos_api.pb_view_switch_router import router as pb_view_switch_router
from aos_api.pb_virtual_data_gen_router import router as pb_virtual_data_gen_router
from aos_api.pp_chart_drag_select_router import router as pp_chart_drag_select_router
from aos_api.pp_chart_pan_router import router as pp_chart_pan_router
from aos_api.pp_cross_project_flow_router import router as pp_cross_project_flow_router
from aos_api.pp_mediasets_code_router import router as pp_mediasets_code_router
from aos_api.pp_parse_paths_router import router as pp_parse_paths_router
from aos_api.pp_role_permission_router import router as pp_role_permission_router
from aos_api.pp_toolbar_share_router import router as pp_toolbar_share_router
from aos_api.wk_conditional_section_router import router as wk_conditional_section_router
from aos_api.wk_widget_permission_router import router as wk_widget_permission_router


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
    application.include_router(dc_completion_strategy.router)
    application.include_router(dc_stream_mgmt.router)
    application.include_router(dc_erp_crm.router)
    application.include_router(di_view_lineage.router)
    application.include_router(di_task_debug.router)
    application.include_router(dl_build_strategy.router)
    application.include_router(dl_build_preview.router)
    application.include_router(dl_dep_order.router)
    application.include_router(dl_stale_diagnosis.router)
    application.include_router(ds_context_menu.router)
    application.include_router(pp_toolbar_settings.router)
    application.include_router(pb_build_vs_deploy.router)
    application.include_router(pb_build_profiles.router)
    application.include_router(pb_task_groups.router)
    application.include_router(pb_health_checks.router)
    application.include_router(cr_branch_menu.router)
    application.include_router(cr_pipeline_review.router)
    application.include_router(ms_header_extractor.router)
    application.include_router(ob_index_debug.router)
    application.include_router(es_sap_stream.router)
    application.include_router(id_py_transform_preview.router)
    application.include_router(id_build_panel.router)
    application.include_router(id_build_status.router)
    application.include_router(af_action_types_router)
    application.include_router(af_capabilities_router)
    application.include_router(af_edit_counter_router)
    application.include_router(af_edited_marker_router)
    application.include_router(af_oma_editor_router)
    application.include_router(af_param_help_router)
    application.include_router(at_action_apply_perm_router)
    application.include_router(at_edit_only_mode_router)
    application.include_router(at_marketplace_types_router)
    application.include_router(at_notification_link_router)
    application.include_router(at_notification_permission_router)
    application.include_router(at_side_effect_perm_router)
    application.include_router(bd_dep_task_abort_router)
    application.include_router(bd_force_build_router)
    application.include_router(bd_freshness_router)
    application.include_router(cr_build_affected_router)
    application.include_router(cr_default_branch_router)
    application.include_router(cr_fallback_branch_router)
    application.include_router(cr_impact_analysis_router)
    application.include_router(dc_agent_yaml_router)
    application.include_router(dc_app_state_router)
    application.include_router(dc_curl_import_router)
    application.include_router(dc_export_tasks_router)
    application.include_router(dc_stream_preview_router)
    application.include_router(dc_sync_troubleshoot_router)
    application.include_router(dc_test_connection_router)
    application.include_router(dc_webhook_source_router)
    application.include_router(di_auto_dedup_router)
    application.include_router(di_auto_register_router)
    application.include_router(di_compression_toggle_router)
    application.include_router(di_consistency_guarantee_router)
    application.include_router(di_data_consistency_router)
    application.include_router(di_dataset_branch_router)
    application.include_router(di_db_schema_table_router)
    application.include_router(di_export_config_router)
    application.include_router(di_external_access_router)
    application.include_router(di_external_transforms_router)
    application.include_router(di_force_build_router)
    application.include_router(di_freshness_detect_router)
    application.include_router(di_hot_cold_storage_router)
    application.include_router(di_key_by_router)
    application.include_router(di_latency_sampling_router)
    application.include_router(di_live_archive_router)
    application.include_router(di_logic_change_trigger_router)
    application.include_router(di_output_path_router)
    application.include_router(di_partition_control_router)
    application.include_router(di_permission_roles_router)
    application.include_router(di_primary_key_config_router)
    application.include_router(di_reset_stream_router)
    application.include_router(di_s3_api_router)
    application.include_router(di_source_based_transform_router)
    application.include_router(di_spark_engine_router)
    application.include_router(di_stream_schema_router)
    application.include_router(di_streaming_latency_router)
    application.include_router(di_text_extraction_router)
    application.include_router(di_third_party_access_router)
    application.include_router(di_transforms_external_router)
    application.include_router(di_view_creation_router)
    application.include_router(di_virtual_storage_router)
    application.include_router(di_virtual_table_router)
    application.include_router(dl_branch_aware_router)
    application.include_router(dl_chart_tools_router)
    application.include_router(dl_dataset_preview_300_router)
    application.include_router(dl_faq_troubleshoot_router)
    application.include_router(dl_flow_animation_router)
    application.include_router(dl_node_indicators_router)
    application.include_router(dl_permission_coloring_router)
    application.include_router(dl_permission_simulation_router)
    application.include_router(dl_plan_management_router)
    application.include_router(dl_property_histogram_router)
    application.include_router(dl_related_artifacts_router)
    application.include_router(dl_share_permission_router)
    application.include_router(dl_stale_coloring_router)
    application.include_router(dl_svg_export_router)
    application.include_router(dl_user_permission_view_router)
    application.include_router(ds_backtick_search_router)
    application.include_router(ds_inline_upload_router)
    application.include_router(fn_pipeline_status_router)
    application.include_router(id_feature_matrix_router)
    application.include_router(id_osdk_react_router)
    application.include_router(ms_create_pipeline_menu_router)
    application.include_router(ms_file_add_router)
    application.include_router(ob_agg_precision_router)
    application.include_router(ob_monitor_notify_router)
    application.include_router(ob_stream_permission_router)
    application.include_router(oc_destructive_confirm_router)
    application.include_router(oc_global_search_router)
    application.include_router(oc_metric_toggle_router)
    application.include_router(oc_org_level_toggle_router)
    application.include_router(oc_permission_migration_router)
    application.include_router(oc_sidebar_filter_router)
    application.include_router(oe_admin_config_router)
    application.include_router(oe_app_sidebar_router)
    application.include_router(oe_column_config_router)
    application.include_router(pb_add_data_modes_router)
    application.include_router(pb_ai_functions_router)
    application.include_router(pb_branch_activity_router)
    application.include_router(pb_branch_version_router)
    application.include_router(pb_color_groups_router)
    application.include_router(pb_data_expectations_router)
    application.include_router(pb_detail_sidebar_router)
    application.include_router(pb_export_java_router)
    application.include_router(pb_fp_growth_router)
    application.include_router(pb_history_records_router)
    application.include_router(pb_marketplace_pkg_router)
    application.include_router(pb_override_dataset_router)
    application.include_router(pb_param_system_router)
    application.include_router(pb_show_hide_nodes_router)
    application.include_router(pb_snapshot_incremental_router)
    application.include_router(pb_structured_semi_router)
    application.include_router(pb_transform_library_router)
    application.include_router(pb_unit_test_router)
    application.include_router(pb_view_switch_router)
    application.include_router(pb_virtual_data_gen_router)
    application.include_router(pp_chart_drag_select_router)
    application.include_router(pp_chart_pan_router)
    application.include_router(pp_cross_project_flow_router)
    application.include_router(pp_mediasets_code_router)
    application.include_router(pp_parse_paths_router)
    application.include_router(pp_role_permission_router)
    application.include_router(pp_toolbar_share_router)
    application.include_router(wk_conditional_section_router)
    application.include_router(wk_widget_permission_router)
    log.info("aos-api_app_created version=%s", application.version)
    return application


app = create_app()
