# Eval 已有预留完整 hash 修复

Rules：231八步、先计划/Task/Lease、原生RED后最小变更；不改原迁移、不可变行、租户、审批、价格、费用、桶算法。父证据Task原生RED：当前原hold未拒绝runtime在新隔离库INSERT的错误contentHash，外层回滚后0行，Provider0。

修改 services/aos-api/aos_api/aip_model_eval_budget_reservation.py：用当前精确申请/审批构造原immutable payload；新hold保持原payload/hash不变，已有hold必须重算存储行完整payload并同时匹配当前预期payload。显式字段缺失/类型错误拒绝，合法重放仍不重复占桶。新增 services/aos-api/tests/aip/test_model_eval_budget_reservation_integrity.py：正确行/单字段漂移/一致重算却错误来源/缺失字段拒绝。

新证据目录使用独立冻结fixture克隆，在新随机aos_test库重跑原申请审批、实际runtime坏hashINSERT及完整hold拒绝，全部rollback；另用原完整申请验证准确hold和replay。无真实Provider/服务部署/当前库改动。专项后相邻原budget contracts/Model Eval authorization/action unit回归；native前缀不等于可执行Model授权。浏览器无产品UI变更不适用。复审/Delivery/仅精确文件本地m1提交/上下文同步；不push，不收口父Task/Goal。
