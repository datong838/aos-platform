# 正式事件审批绑定与a0v057部署

代码c1566d36。三类事件契约与旧cutover契约18passed；真实AIP创建/审批和执行端资格复验4passed；包含权限/锁的专项5passed；真实签名EventControlDispatch服务（改为真实create_proposal）与旧内部cutover审批回归15passed。部署边界8passed。

权限边界：正式AIP连接session_user=aos_app/current_user=aos_runtime；无Case/Policy直接UPDATE，因此新增仅锁固定当前租户Case/Policy头的a0v057函数。无审批事件时不再误用a0v041执行阶段函数。非runtime和跨租户拒绝，并发更新被锁，原表权限不扩大。

独立备份6087957字节，恢复库aos_event_proposal_lock_20260916_test匹配542张旧表。主库同事务迁移前后542表一致，版本057，runtime仅获函数EXECUTE，PUBLIC无EXECUTE，Case/Policy UPDATE仍false。状态/备份/事务证明保留于/Users/ddt/work/projects/ai_agent/.aos-recovery-20260916/state/event-proposal-lock-deployment。

API86172→89367，受控预检GREEN、OpenAPI200。Host83243未重启，F仍binding6/epoch3enabledready、unfenced，canary0。运行日志与intent/result在growth-1.9-current-package/install/product-api057-*。

旧事件审批的NULL binding不回填；旧两次Policy失败请求保留。下一波生成F后继selection/control及绑定，形成新的事件Policy提案并正式审批。Case仍是真实栖月汇全店基线与商品尖刀验证，经营闭环尚未完成。
