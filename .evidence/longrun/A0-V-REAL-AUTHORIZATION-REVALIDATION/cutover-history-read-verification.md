# 全阶段历史恢复视图验证

基线19aeae36；新增六阶段场景先6 failed（无方法），实现后联合29 passed。隔离真实PG覆盖prepare/pause/commit/validate/resume及回滚fence/drain/rollback；原键权限、错误租户/安装、错误hash继续通过。通过读取接口注入缺失event和错误前序引用，均拒绝。未修改不可变历史约束。AR2扫描1826，五类错误空，diff检查通过。

复用各阶段现有解码器，新增prepare事件、阶段完整性及父子引用校验；共用同一当前权限和serializable事务。无真实业务切换、无数据写入、API未重载。此处阶段完成证明来自隔离PG，不冒充栖月汇实际业务完成。

下一波：产品GET恢复接口与安全错误映射，随后受控重载API，浏览器核验当前运行视图；写接口需当前权限与exact审批，不能直接暴露Store幂等返回。
