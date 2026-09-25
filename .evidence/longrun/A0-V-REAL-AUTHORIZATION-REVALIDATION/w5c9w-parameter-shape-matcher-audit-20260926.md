# W5c9w｜六组参数形状的有效 matcher 只读审计

方案 `m1@7277f214`。一次隔离短命进程装配有效路由，不进入 lifespan/端口/数据库/商城源；对下列代表 `scope` 仅调用 `_effective_route.matches(scope)`，未调用 GET/PUT/POST handler。结果每组恰有两条 `Match.FULL`，顺序均为先注册者、后注册者；两条均 `include_in_schema=True`，两套字面模板均出现在 OpenAPI。

| 代表 method/path | 第一条 FULL | 第二条 FULL |
| --- | --- | --- |
| GET `/v1/aip/lineage/probe` | `/v1/aip/lineage/{lineage_id}` `runtime_write.get_lineage` | `/v1/aip/lineage/{record_id}` `phase3_aip_lineage.get_lineage` |
| GET `/v1/ontology/object-types/probe` | `/v1/ontology/object-types/{type_id}` `ontology.get_object_type` | `/v1/ontology/object-types/{ot_id}` `phase4_ontology_types.get_object_type` |
| PUT `/v1/ontology/object-types/probe` | 同前 `ontology.update_object_type` | 同前 `phase4_ontology_types.update_object_type` |
| GET `/v1/schedules/probe` | `/v1/schedules/{schedule_id}` `wave_ext.get_schedule` | `/v1/schedules/{sc_id}` `phase5_schedules.get_schedule` |
| GET `/v1/schedules/probe/runs` | `/v1/schedules/{schedule_id}/runs` `wave_ext.list_schedule_runs` | `/v1/schedules/{sc_id}/runs` `phase5_schedules.list_schedule_runs` |
| POST `/v1/schedules/probe/run` | `/v1/schedules/{schedule_id}/run` `wave_ext.run_schedule` | `/v1/schedules/{sc_id}/run` `phase5_schedules.run_schedule` |

静态审显示第一条 `wave_ext.run_schedule` 可手工触发真实 pipeline，因此本波严格没有向它发请求。上述结果只证明所列代表路径的 matcher 行为，并非所有可能参数值或线上已重载的证明；不把 OpenAPI 双列视为两条可达业务端点。下一波先处理四组 GET 的后置文档权威，再独立处理 PUT/POST 两组写方法，均以不调用 handler 的负例锁住 route 顺序和 schema。原 A0-V 十二 Run 的 row proof/Fleet/Owner/ACK/closure 仍无权威。
