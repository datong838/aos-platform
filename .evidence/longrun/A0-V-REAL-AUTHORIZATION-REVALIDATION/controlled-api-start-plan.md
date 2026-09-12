# 本机受控API启动方案

2026-09-13，97423c73；Lease A0V-CONTROLLED-API-START-20260913。新scripts/a0v_controlled_api.py，固定127.0.0.1:18181和已部署aos_meta_head，保留原aos_app本地诊断元数据连接；受控任务使用受保护runtime-host-identities.json中的独立runtime身份，Host Web身份只作为隔离探针。先检查Lease/m1、文件权限、固定Niushop1.4 signed-bundle root及trust roots；数据库密码只在内存，禁止导出环境/日志。此环境不是生产Web身份验收。

明确关闭迁移、第二Runtime Host、Cron、AIP自动执行、模型健康维护、启动SSH预热；注册executor/resolver由产品main受管启动自行完成。新启动器不种数据、不直接改Pipeline缓存、不替换源或执行函数。check只读诊断元数据身份、runtime身份、隔离探针、主库/新表/服务器factory可装配事实，无源调用或运行记录创建。serve先check，再正常uvicorn启动。旧API仅在检查通过后按已确认PID优雅停止，确认18181释放后替换；保留旧启动器以便受控回退。Host v15不重启。

新测试services/aos-api/tests/test_a0v_controlled_api.py覆盖必要开关、Lease在环境修改前拒绝。实际验证：受管启动注册日志、健康、控制接口及真实登录principal的租户边界；状态变化均写证据。这里不启用计划/读源，后续SourceSelection、Control、计划创建/绑定/启用另按真实合同执行。

预检纠正（17:58Z现场）：现有aos_a0v_web_20260912没有app/runtime成员权限，这是Host隔离身份；本地旧API实际使用aos_app（superuser/bypassrls），请求db.connect再按TenantScope采纳aos_runtime。不能把这个隔离身份冒充已接入整个legacy API的生产Web角色。本波保留原aos_app本地诊断元数据连接（既有受保护读取方法），受控Source/对象入库仍独立runtime连接；不向隔离Web身份授予权限，不改共享角色。启动检查应明确localDiagnostic=true及metadata特权事实，不能命名为生产Web身份GREEN。生产API元数据身份/权限分离登记为发布前独立待办，不阻止本地受控首链开发，但禁止据此发布。原错误预检保留controlled-api-preflight-web-role-rejected.json。
