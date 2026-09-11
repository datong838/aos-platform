# 经营参谋包内分析来源合同验证

2026-09-11，基线 `23ecdc29`。新增包模块与 17 项专项正负测试；与宿主旧来源实现及已迁入的 proposal、structure case、structure eval 相邻合同联合运行共 `118 passed / 1 skipped`，4.67 秒。skip 是原有、需显式 `AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1` 的真实 Bundle/Disclosure 图测试，本切片未放宽。

系统重启后首次测试使用了不存在的根目录 `.venv`，未进入测试。改用仓库实际 `services/aos-api/.venv` 后，测试数据库端口 5433 未启动，101 项在 session setup 阶段被连接拒绝，未执行断言。依据既有授权恢复 Docker 和 `aos-dev-pg`，健康状态为 healthy。第一次实际执行为 `100 passed / 1 failed`，失败揭示严格模型不能解析宿主真实返回的 ISO 时间字符串；修复为显式 ISO 解析并拒绝无时区值。同步复核发现 Disclosure grants 是无序授权集合，材料顺序应由宿主 EvidenceBundle owner 决定，因此改为集合覆盖校验并保留宿主材料顺序。最终联合复跑 `100 passed`。

包模块无 `aos_api`、psycopg 或数据库导入；py_compile 通过。`verify_closure.py --phase ar2-7` 扫描 1762 个 Python 模块、分类 123、迁移集合 85，所有 hash、反向调用、跨层导入和动态引用错误为空。包只对宿主已经授权读取的材料做二次完整性校验，不签发 Disclosure、不持有凭据、不读取数据库、不触发 Provider。宿主 source port、当前 Owner 读取、成功 Attempt 原 query 绑定和生产 Eval target 装配仍待后继切片。

下一步：以本合同为输入边界，建立宿主受控 source port，并把当前成功 AgentRun 的原始 query/Artifact、包内 structure case 和正式 Eval target 绑定到同一事务与 exact refs。
