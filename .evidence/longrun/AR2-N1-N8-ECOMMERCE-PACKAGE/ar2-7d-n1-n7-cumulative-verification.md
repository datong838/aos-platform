# AR2-7D N1～N7 累计受影响集验证

日期：2026-09-10
分支：`m1`
基线：`9766ab75`
结论：`AR2_7D_N1_N7_CUMULATIVE_GREEN`

## 1. 取集规则

- 从 2026-09-07 起至当前基线的 AR2 提交历史提取 `services/aos-api/tests/**/*.py`，去重得到 56 个直接受影响文件。
- `tests/asset_registry` 与 `tests/extension_runtime` 共 36 个测试/辅助文件已由同一基线前一切片的 `868 passed` 和 `1280 passed` 全量覆盖。
- 本次串行运行其余 20 个文件，覆盖 N1～N7 的预算预留、配置修订与观察、DataRequirement、规范人口、商品比较/联合质量、Router manifest、JDBC 私有源边界和生产合同存储。

## 2. 正确隔离路径

- PostgreSQL 管理入口固定为 `aos_test@127.0.0.1:18434/aos_test_admin`。
- 不设置 `AOS_TEST_USE_SHARED_DATABASE`；根级 session fixture 创建唯一 `aos_test_<uuid>_ti4_test` 数据库，完整迁移后运行测试，并在 finally 中终止连接、删除数据库。
- 全程一个 pytest 进程，不与其他 PostgreSQL 测试并行；不访问真实源、Provider 或真实租户，不执行共享/生产迁移。

## 3. 最终结果

`294 passed, 10 warnings, 2 subtests passed in 42.00s`

退出码为 0。测试结束后核验：

- `pg_database` 中不存在 `aos_test_%_ti4_test` 残留；
- 管理库中不存在 `aos_ext_%` 或 `ar2_%` 临时 schema；
- 工作树无本切片代码修改。

10 条 warning 为既有 Pydantic 字段遮蔽、Starlette TestClient 弃用，以及故意构造非法 enum/引用值时的 serializer warning；没有失败或新增外部副作用。

## 4. 失败路径记录

- 首次命令把换行路径放入 zsh 标量，pytest 在收集前以“file or directory not found”退出，`no tests ran`；改为 zsh 数组逐项传参。
- 第二次误设 `AOS_TEST_USE_SHARED_DATABASE=1`，根级 fixture 按合同跳过一次性建库/迁移，结果为 `113 failed / 181 passed`，失败均集中在 `meta_source`、`twa_org` 等基础表不存在。该运行没有建立或修改共享表，不作为逻辑回归结果。
- 去掉 shared 标志、恢复仓库标准隔离入口后，同一 20 文件集合一次全绿；未通过补表、跳测或扩大权限制造结果。

## 5. 下一步

继续 AR2-7D Web 全量单测、TypeScript/生产构建与资产控制三视口验收。`ar2-7` 的十项 Router/Web 最终切换红项仍保持未关闭，不能提前推进 `AOS-000571` 或宣布整波 7D GREEN。
