# SC4-3c2 启动预览验证

2026-09-14，m1 单写者。方案：analysis-bootstrap-runtime-design.md。

新增 Host 服务 ecommerce_analysis_startup_preview.py，在原来源与编译事务内保存可回读初始化意图 Evidence，再通过原 Store 创建、冻结并复核本 Task/Plan/Context 的 ImpactPreview。有效期不滑动延长，当前职责版本、Binding版本及来源均须一致；回调后复核，任何故障随编译整体回滚。本波没有批准 Action、创建 TaskRun、调用模型或部署主安装。

验证：首次缺模块红测；版本漂移新增用例确认 DID NOT RAISE 后修复。最终精确五组测试（startup_preview_pg、bootstrap_contract、compilation_preparation_pg、initial_checkpoint_pg、w2d_start_gate）34 passed，7条既有警告，10.29秒。日志 /tmp/a0v-startup-preview-final2.log。覆盖冻结正文、可回读来源、零调用初始化边界、撤销、绑定漂移、职责版本漂移、下游回滚；原启动门与检查点回归保留。

AR2 ar2-7：1901模块/179分类/93迁移，五类错误为空。memory validate GREEN：AOS-000573，1100 Delivery、1083 Task、2699事件。

限制：仅隔离 PostgreSQL 实证；来源、模型可用性和配置含明确 fixture，未证明主租户真实首链。初始化影响声明不是经营质量评估或商业成本结论。下一波 SC4-3c3 专用当前授权守卫及启动门整合，之后 c4 运行组合与 SC4-4 正式事件 START。
