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
from aos_api.di_stream_alert_router import router as di_stream_alert_router
from aos_api.di_monitor_rule_router import router as di_monitor_rule_router
from aos_api.di_notif_sub_router import router as di_notif_sub_router
from aos_api.di_checkpoint_ft_router import router as di_checkpoint_ft_router
from aos_api.di_backing_ds_router import router as di_backing_ds_router
from aos_api.di_live_log_router import router as di_live_log_router
from aos_api.di_schema_config_router import router as di_schema_config_router
from aos_api.di_detail_subpanel_router import router as di_detail_subpanel_router
from aos_api.dh_health_summary_router import router as dh_health_summary_router
from aos_api.dh_troubleshoot_guide_router import router as dh_troubleshoot_guide_router
from aos_api.dl_ontology_browse_router import router as dl_ontology_browse_router
from aos_api.dl_history_detail_router import router as dl_history_detail_router
from aos_api.dl_save_open_chart_router import router as dl_save_open_chart_router
from aos_api.dl_share_link_router import router as dl_share_link_router
from aos_api.ds_schedule_panel_router import router as ds_schedule_panel_router
from aos_api.ds_share_move_rename_router import router as ds_share_move_rename_router
from aos_api.ds_stream_preview_router import router as ds_stream_preview_router
from aos_api.ds_stream_tag_router import router as ds_stream_tag_router
from aos_api.ds_schema_infer_router import router as ds_schema_infer_router
from aos_api.ds_edit_schema_view_router import router as ds_edit_schema_view_router
from aos_api.ds_col_autocomplete_router import router as ds_col_autocomplete_router
from aos_api.ds_keyboard_shortcut_router import router as ds_keyboard_shortcut_router
from aos_api.ds_resize_panel_router import router as ds_resize_panel_router
from aos_api.ds_same_name_logic_router import router as ds_same_name_logic_router
from aos_api.ds_sql_draft_router import router as ds_sql_draft_router
from aos_api.pp_incremental_perf_router import router as pp_incremental_perf_router
from aos_api.pp_schema_infer_router import router as pp_schema_infer_router
from aos_api.pp_advanced_schedule_router import router as pp_advanced_schedule_router
from aos_api.pp_schedule_troubleshoot_router import router as pp_schedule_troubleshoot_router
from aos_api.pp_schedule_best_practice_router import router as pp_schedule_best_practice_router
from aos_api.pp_schedule_template_router import router as pp_schedule_template_router
from aos_api.pp_classify_tag_router import router as pp_classify_tag_router
from aos_api.pp_propagate_view_router import router as pp_propagate_view_router
from aos_api.pp_org_tag_router import router as pp_org_tag_router
from aos_api.pp_tag_reapproval_router import router as pp_tag_reapproval_router
from aos_api.pp_io_classify_router import router as pp_io_classify_router
from aos_api.pp_schedule_coloring_router import router as pp_schedule_coloring_router
from aos_api.pp_folder_convention_router import router as pp_folder_convention_router
from aos_api.pp_dev_best_practice_router import router as pp_dev_best_practice_router
from aos_api.pp_prod_pipeline_build_router import router as pp_prod_pipeline_build_router
from aos_api.pp_connect_stream_router import router as pp_connect_stream_router
from aos_api.pb_breaking_change_detect_router import router as pb_breaking_change_detect_router
from aos_api.cr_model_dev_repo_router import router as cr_model_dev_repo_router
from aos_api.cr_doc_assist_router import router as cr_doc_assist_router
from aos_api.cr_pr_review_router import router as cr_pr_review_router
from aos_api.cr_code_review_req_router import router as cr_code_review_req_router
from aos_api.cr_dataset_alias_router import router as cr_dataset_alias_router
from aos_api.cr_multi_artifact_router import router as cr_multi_artifact_router
from aos_api.cr_artifact_credential_router import router as cr_artifact_credential_router
from aos_api.cr_artifact_registry_router import router as cr_artifact_registry_router
from aos_api.cr_ai_error_enhance_router import router as cr_ai_error_enhance_router
from aos_api.cr_aip_template_recommend_router import router as cr_aip_template_recommend_router
from aos_api.mt_code_reuse_router import router as mt_code_reuse_router
from aos_api.ms_small_file_shortcut_router import router as ms_small_file_shortcut_router
from aos_api.ms_docintel_dlq_router import router as ms_docintel_dlq_router
from aos_api.ms_latency_policy_router import router as ms_latency_policy_router
from aos_api.ms_transcript_postproc_router import router as ms_transcript_postproc_router
from aos_api.ms_transcript_output_router import router as ms_transcript_output_router
from aos_api.ms_audio_import_path_router import router as ms_audio_import_path_router
from aos_api.ms_primary_key_router import router as ms_primary_key_router
from aos_api.oe_pivot_linked_router import router as oe_pivot_linked_router
from aos_api.oe_compare_objects_router import router as oe_compare_objects_router
from aos_api.oe_metadata_state_router import router as oe_metadata_state_router
from aos_api.oe_render_hint_router import router as oe_render_hint_router
from aos_api.oe_gotham_integration_router import router as oe_gotham_integration_router
from aos_api.oe_linked_view_router import router as oe_linked_view_router
from aos_api.oe_version_mgmt_router import router as oe_version_mgmt_router
from aos_api.oe_comment_system_router import router as oe_comment_system_router
from aos_api.oc_model_aiml_router import router as oc_model_aiml_router
from aos_api.oc_audit_edit_dialog_router import router as oc_audit_edit_dialog_router
from aos_api.oc_task_model_router import router as oc_task_model_router
from aos_api.oc_review_view_router import router as oc_review_view_router
from aos_api.oc_compute_attribution_router import router as oc_compute_attribution_router
from aos_api.oc_cross_ontology_migrate_router import router as oc_cross_ontology_migrate_router
from aos_api.oc_ontology_switcher_router import router as oc_ontology_switcher_router
from aos_api.ob_billion_throughput_router import router as ob_billion_throughput_router
from aos_api.ob_osv1_osv2_router import router as ob_osv1_osv2_router
from aos_api.ob_batch_reindex_router import router as ob_batch_reindex_router
from aos_api.ob_index_monitor_router import router as ob_index_monitor_router
from aos_api.ob_object_monitor_router import router as ob_object_monitor_router
from aos_api.ob_realtime_eval_router import router as ob_realtime_eval_router
from aos_api.ob_monitor_to_action_router import router as ob_monitor_to_action_router
from aos_api.ob_monitor_activity_router import router as ob_monitor_activity_router
from aos_api.ob_granular_policy_router import router as ob_granular_policy_router
from aos_api.ob_edit_history_router import router as ob_edit_history_router
from aos_api.ob_inline_edit_router import router as ob_inline_edit_router
from aos_api.if_interface_metadata_router import router as if_interface_metadata_router
from aos_api.af_archetypes_toggle_router import router as af_archetypes_toggle_router
from aos_api.at_param_desc_router import router as at_param_desc_router
from aos_api.at_value_source_router import router as at_value_source_router
from aos_api.at_rule_order_conflict_router import router as at_rule_order_conflict_router
from aos_api.at_oma_7tab_router import router as at_oma_7tab_router
from aos_api.at_archetypes_toggle_router import router as at_archetypes_toggle_router
from aos_api.at_edit_count_warn_router import router as at_edit_count_warn_router
from aos_api.at_edited_marker_router import router as at_edited_marker_router
from aos_api.at_func_op_types_router import router as at_func_op_types_router
from aos_api.at_func_onboarding_router import router as at_func_onboarding_router
from aos_api.ca_platform_facade_router import router as ca_platform_facade_router
from aos_api.ca_heavy_capability_router import router as ca_heavy_capability_router
from aos_api.sc_logic_change_trigger_router import router as sc_logic_change_trigger_router
from aos_api.sc_calendar_view_router import router as sc_calendar_view_router
from aos_api.sc_readonly_dynamic_router import router as sc_readonly_dynamic_router
from aos_api.sc_dynamic_drag_drop_router import router as sc_dynamic_drag_drop_router
from aos_api.gs_ontology_geo_router import router as gs_ontology_geo_router
from aos_api.rl_rule_workflow_router import router as rl_rule_workflow_router
from aos_api.rl_transform_pipeline_rule_router import router as rl_transform_pipeline_rule_router
from aos_api.rl_workshop_integration_router import router as rl_workshop_integration_router
from aos_api.wk_overlay_router import router as wk_overlay_router
from aos_api.wk_object_table_advanced_router import router as wk_object_table_advanced_router
from aos_api.vs_module_interface_router import router as vs_module_interface_router
from aos_api.vs_events_router import router as vs_events_router
from aos_api.vs_event_idempotent_router import router as vs_event_idempotent_router
from aos_api.es_auto_ontology_gen_router import router as es_auto_ontology_gen_router
from aos_api.cp_multi_spoke_monitor_router import router as cp_multi_spoke_monitor_router
from aos_api.au_policy_hot_reload_router import router as au_policy_hot_reload_router
from aos_api.id_shell_terminal_router import router as id_shell_terminal_router
from aos_api.id_key_binding_router import router as id_key_binding_router
from aos_api.id_vsix_install_router import router as id_vsix_install_router
from aos_api.id_command_palette_router import router as id_command_palette_router
from aos_api.id_python_snippet_router import router as id_python_snippet_router
from aos_api.id_refresh_token_router import router as id_refresh_token_router
from aos_api.id_install_python_env_router import router as id_install_python_env_router
from aos_api.id_public_extension_router import router as id_public_extension_router
from aos_api.di_virtual_table_create_router import router as di_virtual_table_create_router
from aos_api.dh_escalate_router import router as dh_escalate_router
from aos_api.pb_expr_func_index_router import router as pb_expr_func_index_router
from aos_api.cr_transform_repo_router import router as cr_transform_repo_router
from aos_api.cr_editor_context_menu_router import router as cr_editor_context_menu_router
from aos_api.cr_spark_profiles_router import router as cr_spark_profiles_router
from aos_api.cr_docker_artifact_publish_router import router as cr_docker_artifact_publish_router
from aos_api.cr_code_autocomplete_router import router as cr_code_autocomplete_router
from aos_api.mt_python_transform_df_router import router as mt_python_transform_df_router
from aos_api.mt_java_transform_api_router import router as mt_java_transform_api_router
from aos_api.mt_r_transform_router import router as mt_r_transform_router
from aos_api.mt_spark_version_mgmt_router import router as mt_spark_version_mgmt_router
from aos_api.mt_unit_test_router import router as mt_unit_test_router
from aos_api.mt_data_expectations_router import router as mt_data_expectations_router
from aos_api.ms_java_transform_integration_router import router as ms_java_transform_integration_router
from aos_api.ms_form_parser_router import router as ms_form_parser_router
from aos_api.ms_multi_sheet_output_router import router as ms_multi_sheet_output_router
from aos_api.ms_incremental_process_router import router as ms_incremental_process_router
from aos_api.ms_error_dataframe_router import router as ms_error_dataframe_router
from aos_api.ms_spark_mem_config_router import router as ms_spark_mem_config_router
from aos_api.ms_api_javadoc_router import router as ms_api_javadoc_router
from aos_api.oc_shared_ontology_router import router as oc_shared_ontology_router
from aos_api.gs_geospatial_framework_router import router as gs_geospatial_framework_router
from aos_api.gs_coord_projection_router import router as gs_coord_projection_router
from aos_api.gs_map_layer_overlay_router import router as gs_map_layer_overlay_router
from aos_api.gs_map_template_router import router as gs_map_template_router
from aos_api.gs_digital_twin_engine_router import router as gs_digital_twin_engine_router
from aos_api.gs_causal_analysis_router import router as gs_causal_analysis_router
from aos_api.gs_realtime_situation_router import router as gs_realtime_situation_router
from aos_api.gs_timeseries_object_type_router import router as gs_timeseries_object_type_router
from aos_api.gs_sensor_data_model_router import router as gs_sensor_data_model_router
from aos_api.wk_embedded_copilot_router import router as wk_embedded_copilot_router
from aos_api.vs_timeseries_set_router import router as vs_timeseries_set_router
from aos_api.es_sap_batch_import_router import router as es_sap_batch_import_router
from aos_api.es_derived_element_intel_router import router as es_derived_element_intel_router
from aos_api.hs_remote_dispatch_router import router as hs_remote_dispatch_router
from aos_api.hs_status_report_back_router import router as hs_status_report_back_router
from aos_api.fr2_incremental_package_router import router as fr2_incremental_package_router
from aos_api.cp_realtime_situation_router import router as cp_realtime_situation_router
from aos_api.cp_alert_router import router as cp_alert_router
from aos_api.id_geospatial_framework_router import router as id_geospatial_framework_router
from aos_api.id_vertex_digital_twin_router import router as id_vertex_digital_twin_router
from aos_api.id_timeseries_router import router as id_timeseries_router
from aos_api.zz_property_editor_router import router as zz_property_editor_router
from aos_api.zz_function_type_editor_router import router as zz_function_type_editor_router
from aos_api.zz_multi_source_heterogeneous_router import router as zz_multi_source_heterogeneous_router
from aos_api.zz_graph_health_router import router as zz_graph_health_router


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
    application.include_router(di_stream_alert_router)
    application.include_router(di_monitor_rule_router)
    application.include_router(di_notif_sub_router)
    application.include_router(di_checkpoint_ft_router)
    application.include_router(di_backing_ds_router)
    application.include_router(di_live_log_router)
    application.include_router(di_schema_config_router)
    application.include_router(di_detail_subpanel_router)
    application.include_router(dh_health_summary_router)
    application.include_router(dh_troubleshoot_guide_router)
    application.include_router(dl_ontology_browse_router)
    application.include_router(dl_history_detail_router)
    application.include_router(dl_save_open_chart_router)
    application.include_router(dl_share_link_router)
    application.include_router(ds_schedule_panel_router)
    application.include_router(ds_share_move_rename_router)
    application.include_router(ds_stream_preview_router)
    application.include_router(ds_stream_tag_router)
    application.include_router(ds_schema_infer_router)
    application.include_router(ds_edit_schema_view_router)
    application.include_router(ds_col_autocomplete_router)
    application.include_router(ds_keyboard_shortcut_router)
    application.include_router(ds_resize_panel_router)
    application.include_router(ds_same_name_logic_router)
    application.include_router(ds_sql_draft_router)
    application.include_router(pp_incremental_perf_router)
    application.include_router(pp_schema_infer_router)
    application.include_router(pp_advanced_schedule_router)
    application.include_router(pp_schedule_troubleshoot_router)
    application.include_router(pp_schedule_best_practice_router)
    application.include_router(pp_schedule_template_router)
    application.include_router(pp_classify_tag_router)
    application.include_router(pp_propagate_view_router)
    application.include_router(pp_org_tag_router)
    application.include_router(pp_tag_reapproval_router)
    application.include_router(pp_io_classify_router)
    application.include_router(pp_schedule_coloring_router)
    application.include_router(pp_folder_convention_router)
    application.include_router(pp_dev_best_practice_router)
    application.include_router(pp_prod_pipeline_build_router)
    application.include_router(pp_connect_stream_router)
    application.include_router(pb_breaking_change_detect_router)
    application.include_router(cr_model_dev_repo_router)
    application.include_router(cr_doc_assist_router)
    application.include_router(cr_pr_review_router)
    application.include_router(cr_code_review_req_router)
    application.include_router(cr_dataset_alias_router)
    application.include_router(cr_multi_artifact_router)
    application.include_router(cr_artifact_credential_router)
    application.include_router(cr_artifact_registry_router)
    application.include_router(cr_ai_error_enhance_router)
    application.include_router(cr_aip_template_recommend_router)
    application.include_router(mt_code_reuse_router)
    application.include_router(ms_small_file_shortcut_router)
    application.include_router(ms_docintel_dlq_router)
    application.include_router(ms_latency_policy_router)
    application.include_router(ms_transcript_postproc_router)
    application.include_router(ms_transcript_output_router)
    application.include_router(ms_audio_import_path_router)
    application.include_router(ms_primary_key_router)
    application.include_router(oe_pivot_linked_router)
    application.include_router(oe_compare_objects_router)
    application.include_router(oe_metadata_state_router)
    application.include_router(oe_render_hint_router)
    application.include_router(oe_gotham_integration_router)
    application.include_router(oe_linked_view_router)
    application.include_router(oe_version_mgmt_router)
    application.include_router(oe_comment_system_router)
    application.include_router(oc_model_aiml_router)
    application.include_router(oc_audit_edit_dialog_router)
    application.include_router(oc_task_model_router)
    application.include_router(oc_review_view_router)
    application.include_router(oc_compute_attribution_router)
    application.include_router(oc_cross_ontology_migrate_router)
    application.include_router(oc_ontology_switcher_router)
    application.include_router(ob_billion_throughput_router)
    application.include_router(ob_osv1_osv2_router)
    application.include_router(ob_batch_reindex_router)
    application.include_router(ob_index_monitor_router)
    application.include_router(ob_object_monitor_router)
    application.include_router(ob_realtime_eval_router)
    application.include_router(ob_monitor_to_action_router)
    application.include_router(ob_monitor_activity_router)
    application.include_router(ob_granular_policy_router)
    application.include_router(ob_edit_history_router)
    application.include_router(ob_inline_edit_router)
    application.include_router(if_interface_metadata_router)
    application.include_router(af_archetypes_toggle_router)
    application.include_router(at_param_desc_router)
    application.include_router(at_value_source_router)
    application.include_router(at_rule_order_conflict_router)
    application.include_router(at_oma_7tab_router)
    application.include_router(at_archetypes_toggle_router)
    application.include_router(at_edit_count_warn_router)
    application.include_router(at_edited_marker_router)
    application.include_router(at_func_op_types_router)
    application.include_router(at_func_onboarding_router)
    application.include_router(ca_platform_facade_router)
    application.include_router(ca_heavy_capability_router)
    application.include_router(sc_logic_change_trigger_router)
    application.include_router(sc_calendar_view_router)
    application.include_router(sc_readonly_dynamic_router)
    application.include_router(sc_dynamic_drag_drop_router)
    application.include_router(gs_ontology_geo_router)
    application.include_router(rl_rule_workflow_router)
    application.include_router(rl_transform_pipeline_rule_router)
    application.include_router(rl_workshop_integration_router)
    application.include_router(wk_overlay_router)
    application.include_router(wk_object_table_advanced_router)
    application.include_router(vs_module_interface_router)
    application.include_router(vs_events_router)
    application.include_router(vs_event_idempotent_router)
    application.include_router(es_auto_ontology_gen_router)
    application.include_router(cp_multi_spoke_monitor_router)
    application.include_router(au_policy_hot_reload_router)
    application.include_router(id_shell_terminal_router)
    application.include_router(id_key_binding_router)
    application.include_router(id_vsix_install_router)
    application.include_router(id_command_palette_router)
    application.include_router(id_python_snippet_router)
    application.include_router(id_refresh_token_router)
    application.include_router(id_install_python_env_router)
    application.include_router(id_public_extension_router)
    application.include_router(di_virtual_table_create_router)
    application.include_router(dh_escalate_router)
    application.include_router(pb_expr_func_index_router)
    application.include_router(cr_transform_repo_router)
    application.include_router(cr_editor_context_menu_router)
    application.include_router(cr_spark_profiles_router)
    application.include_router(cr_docker_artifact_publish_router)
    application.include_router(cr_code_autocomplete_router)
    application.include_router(mt_python_transform_df_router)
    application.include_router(mt_java_transform_api_router)
    application.include_router(mt_r_transform_router)
    application.include_router(mt_spark_version_mgmt_router)
    application.include_router(mt_unit_test_router)
    application.include_router(mt_data_expectations_router)
    application.include_router(ms_java_transform_integration_router)
    application.include_router(ms_form_parser_router)
    application.include_router(ms_multi_sheet_output_router)
    application.include_router(ms_incremental_process_router)
    application.include_router(ms_error_dataframe_router)
    application.include_router(ms_spark_mem_config_router)
    application.include_router(ms_api_javadoc_router)
    application.include_router(oc_shared_ontology_router)
    application.include_router(gs_geospatial_framework_router)
    application.include_router(gs_coord_projection_router)
    application.include_router(gs_map_layer_overlay_router)
    application.include_router(gs_map_template_router)
    application.include_router(gs_digital_twin_engine_router)
    application.include_router(gs_causal_analysis_router)
    application.include_router(gs_realtime_situation_router)
    application.include_router(gs_timeseries_object_type_router)
    application.include_router(gs_sensor_data_model_router)
    application.include_router(wk_embedded_copilot_router)
    application.include_router(vs_timeseries_set_router)
    application.include_router(es_sap_batch_import_router)
    application.include_router(es_derived_element_intel_router)
    application.include_router(hs_remote_dispatch_router)
    application.include_router(hs_status_report_back_router)
    application.include_router(fr2_incremental_package_router)
    application.include_router(cp_realtime_situation_router)
    application.include_router(cp_alert_router)
    application.include_router(id_geospatial_framework_router)
    application.include_router(id_vertex_digital_twin_router)
    application.include_router(id_timeseries_router)
    application.include_router(zz_property_editor_router)
    application.include_router(zz_function_type_editor_router)
    application.include_router(zz_multi_source_heterogeneous_router)
    application.include_router(zz_graph_health_router)
    log.info("aos-api_app_created version=%s", application.version)
    return application


app = create_app()
