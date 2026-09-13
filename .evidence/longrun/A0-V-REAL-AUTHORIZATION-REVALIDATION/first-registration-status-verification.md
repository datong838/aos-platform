# 登记状态发现切片验证｜2026-09-13

基线a8f078a9，m1单写者；属于BG-01，仍未关闭整个任务。

1/6：复核231-9与当前产品目标，当前权限/安装恢复仍为首链前置。
2/6：先扩充first-registration-withdrawal-design.md：无手填key的只读发现，状态不授予动作。
3/6：新增HTTP测试5项RED（接口缺失），随后实现Owner与GET入口。
4/6：真实隔离PG与HTTP联合34项通过；现有权限组合使用fixture，SQL/RLS/Receipt真实，不冒充生产全栈。
5/6：补重登记/租户隔离；最终76 passed、18 warnings，13.22s。日志/tmp/a0v-status-final.log；AR2 ar2-7扫描1821、分类158、迁移93，五类错误均为空。git diff --check通过。
6/6：本片提交；下一波为撤回资格状态和页面入口，再安排主库独立连接/迁移及真实验收。此片不完成BG-01或首链。

变更：ecommerce_growth_registration.py增加registration_status；bundle_runtime_installations.py新增GET /{installation_id}/ecommerce-growth-registrations/status。仅当前有安装控制权限者可查；服务缺失503；无未撤回登记时严格回读最近撤回，否则为无登记。唯一未撤回项返回exact ref，多项needs_attention不猜测。任何状态allowedActions=[]、executable=false。SERIALIZABLE/runtime、明确tenant过滤；不切maintainer、不修改数据、不要求历史key，不暴露完整原请求。

验证局限：本次接口测试使用TestClient，主库迁移及运行进程未改变；未做浏览器验收，因为本片未增加页面。安装store/current permission的组合仍是该隔离PG fixture；不据此宣称生产权限已完成验收。多候选保守分支尚无真实PG场景覆盖，后续资格切片补充。完整首链、八场景、连续观察仍待验收。
