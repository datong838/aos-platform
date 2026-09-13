# D2d-2c 原Host受控装配验证（2026-09-14）

基线85291892，m1原A0-V租约。新增configuration_stage_preflight.py；修改runtime_host.py、production_runtime.py、asset_registry/control_wiring.py及相关测试。

默认configuration_stage_enabled=False；环境仅0/1（缺省0），非法值不组装依赖。打开时才添加原ConfigurationStageConsumer，启动选择先检查新增队列/配置表FORCE RLS、非owner、runtime列级最小权限、无INSERT/DELETE/TRUNCATE/身份UPDATE、守卫启用且非definer。异常返回CONFIGURATION_STAGE_PREFLIGHT_FAILED。原configure/disable/UI消费顺序保持，未增加独立线程进程或重启实际Host。

验证：preflight真实隔离PG以非owner session身份执行，tuple/dict行格式都验证；扩大权限/丢失权限/关闭RLS/关闭触发器均拒绝。Host默认关闭、明确启用且检查通过才加入、检查失败不返回Host、严格bool拒绝。首轮连原production_runtime/runtime_host合计66 passed；环境0/1/invalid补验后production+selection 29 passed。7既有warning，diff检查通过。

运行实测：原PID6606仍存活，读取时累计13小时18分；API18181的/v1/health返回status ok。初次误访问/health返回404，已核对正式路由并使用/v1/health复测，不将404解释为服务故障。未部署036、未改变环境开关、未更换Host/API或主库配置。

限制：正式消费者已能参与受控组装，但本地当前主库仍035，不能开启；缺少受限API收件/结果查询与产品来源选择，真实配置登记到启用尚未验收。下一波次D2d-3专用API收件与原主体查询合同/数据库函数，先做方案和隔离数据库否定验证，再安排真实部署。
