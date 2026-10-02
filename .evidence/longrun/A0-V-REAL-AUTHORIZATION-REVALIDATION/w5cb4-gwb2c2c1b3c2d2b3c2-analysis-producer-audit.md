# GW-b-2c2c1b3c2d2b3c2 原 Analysis producer 预检

基线 `AOS-001130` / `m1 8badf0cf`，只读代码/测试路径调查，当前真实库未写。为接 d2b3c2，查 `test_product_event_analysis_bootstrap_pg.py` 的原 `analysis.handle(claimed)`，其测试原意是在隔离 PG 由原 Store 生成 `AnalysisRuntimeReceipt`、TaskRun 与 compilation Receipt。

在 signed preview preflight 限定的独立 `aos_test_*` DB 上执行 `pytest .../test_product_event_analysis_bootstrap_pg.py -k formal_event_handle_creates_complete_initial_lineage --tb=short`，退出1，1 error/7 deselected。错误在**fixture setup**，尚未运行原 Analysis producer：`publications` → `published_skill_runtime` → `AipReleasePublicationService.derive_gate`，明确拒绝 `formal Skill Eval executor authority unavailable`。代码在 `aip_release_publication_service.py` 对 `SkillTemplate` 目标主动失败关闭。原测试使用选取/已安装计算 fixture，并非当前正式签名/身份验收；改为 `historical_event=True` 会避开这道正式门，不可据此充当当前正式来源。

结论：这条旧测试路径不能直接作为 d2b3c2 正向来源；不能将 setup error 归因于本轮 Owner 引用代码。下一步先盘点已有原 Analysis producer 是否有不经过旧 Skill 发布 fixture 的合法可销毁 PG 路径；如无，按 231 与产品方案补正式 Skill Eval executor/发布来源的文件级方案及 RED。当前实例仍缺 OIDC/Host 凭据、八配置/发布/assignment，不启 Host/worker/Provider，不手工 Run，不回放旧12 Run。
