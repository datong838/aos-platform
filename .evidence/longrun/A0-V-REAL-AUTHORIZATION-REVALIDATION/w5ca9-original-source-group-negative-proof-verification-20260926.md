# W5ca9｜原始源组多组/持久 manifest 篡改隔离负例 verification

1. 上位：231 A0-V→A1、230 L0、W5c8g 只读诊断、`a0v_045` 唯一/不可变合同、W5ca5 no-authority 已复习。
2. 方案 `m1@32d0ec7d` 先提交；`m1@6bf9cd37` 在跑 PG 前纠正测试夹具：标准 `conftest.py` 自动创建/销毁 `aos_test_*_ti4_test`，不能用 `--noconftest`；专用测试 PG 在 `colima-aos-a0v-test-only:5433`，无共享库开关。
3. 仅改 `services/aos-api/tests/extension_runtime/test_a0v_w5c8g_unknown_source_group_read_only_pg.py`。在原完整链/unknown 诊断已完成后，提交第二组相同 Run 成员被 `UniqueViolation` 拒绝；已保存 input manifest 的错误 rowCount UPDATE 被 `extension history is immutable` 拒绝；两失败事务均 rollback，之后原只读证据 group/hash 保持。
4. 无生产代码、迁移或权限变更；无真实组/商城源读取；测试在一次性合成库内执行。
5. 单文件完整原链专项 `1 passed, 7 warnings in 173.49s`；7 警告为现存 Pydantic 字段/Starlette 弃用。测试容器 `aos_test_*` 数据库余量 0；`py_compile`、`git diff --check` 通过。相邻 locator 测试均为 PG、需再次整库 bootstrap，本波没有虚报额外累计；本单文件自身覆盖既有全部正负链。
6. 8080 无业务 listener；18181 `/docs` HTTP200，只是本地文档，不作业务浏览器验收；原 18181 进程未触碰。
7. 一致性：同一 Run 在第二组的提交歧义被数据库唯一键阻断，持久 manifest 更新被不可变触发器阻断；`PipelineSnapshotGroupLocator` 的 `len(rows)!=1` 分支未被强造，不声称历史原始行语义或全机 Host 证明。
8. 本 verification、D-waves、AOS/Prime 记忆、m1 精确提交；不 push。
9. 下一波继续安全独立债；真实原组十二 Run、ACK/closure、历史独立行语义、Fleet/Owner、真库迁移与 230 L0 均未完成。
