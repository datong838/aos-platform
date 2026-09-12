# 管道图重启发现与详情恢复

2026-09-12，基线dc001b81。沿D1正式Pipeline API登记、可恢复目标。本波仅恢复用户保存的图的可见性，不注册执行权限、不启用Cron、不直接灌业务数据。

## 缺口与最小实现

phase5_pipeline_graph已持久保存完整DAG且get_graph可恢复；但列表仅列内存，详情get_pipeline仅查内存。禁用旧bootstrap的正式启动不应靠重新seed修复。采用读路径恢复：

- services/aos-api/aos_api/data_os_store.py新增双租户限定的已保存图目录读取，只投影id/name/type/write_mode，不加载节点配置/凭据、不写库。排序按pipeline_id。
- services/aos-api/aos_api/routers/wave_ext.py在正式列表补齐未列出的持久图，标记draft/disabled及persisted，不冒认niushop来源，不复活metadata中已decommissioned/deleted/archived的同ID管道。
- services/aos-api/aos_api/routers/phase5_pipelines.py详情在内存缺失时调用既有get_graph恢复Owner；无图仍404。不得通过query/body恢复execution_mode/executor授权。
- services/aos-api/tests/test_pipeline_graph_discovery_recovery.py验证保存→清空进程内存→列表发现→详情恢复→同版本图不变、执行禁用、跨租户不可见、退役配置不出列表。使用临时PG数据库，不用真实租户fixture。

此波不解决完整execution配置、首次登记的空配置持久化、删除Owner或自动消费。后续继续P01明确映射、真实执行器注册与当前源/读取治理绑定；不将目录恢复视作同步完成。

## 本波真实只配置验收

在org-org/dev-project通过正式PUT graph接口登记P01-shop-qyh禁用草稿，来源为已评审p01-shop.yaml；只保存Source/Transform/Sink配置及site_id=1、PII排除，不读业务行、不启用执行、不创建调度。写前确认同ID没有图；任何未知响应仅回读、不重发。随后重启API，以正式列表/详情/graph读取证明同ID/同版本/同节点配置仍存在且execution_mode=disabled。若同ID已存在则比较当前图，禁止覆盖。此验收记录不计为P01数据同步成功。
