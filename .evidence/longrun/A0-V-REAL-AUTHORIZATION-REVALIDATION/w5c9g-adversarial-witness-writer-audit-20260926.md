# W5c9g｜恶意自洽输入下的见证写门隔离审计

方案 `m1@d210bb40`，承接 W5c9f 隔离 PG 夹具。只扩展同一一次性 PG 测试：从已提交原 claim/input 精确重建 canonical binding/manifest，创建独立 NOLOGIN/NOBYPASSRLS/NOINHERIT caller 并显式授专用 operator、SET SESSION AUTHORIZATION/SET ROLE、租户 GUC、REPEATABLE READ。错误租户参数先得 `InsufficientPrivilege`；正确精确参数一次调用 `a0v_098` 返回 `INSERTED`。读回 sidecar request/manifest hash 与两段 canonical 文本逐字等于原不可变记录，且文本仍含夹具的错误 rowsHash。测试不调用运行时 ACK/closure，也不查询商城源数据。

首轮 RED 是测试 admin 连接默认 tuple 行却按字典索引回读；函数调用阶段已执行，但该轮不冒充 GREEN。改用 dict_row 后专项 `1 passed, 7 warnings in 113.39s`；相关无 PG 累计 `30 passed, 7 warnings`，一次性 `aos_test_*` DB 0、临时 `aos_test_witness_*` caller 0，`git diff --check` 通过。全仓引用 `pipeline_snapshot_group_canonical_witness_a0v_097`/`a0v_098` 仅迁移与测试，未接应用运行路径。

结论严格限定：`a0v_098` 是**原字节见证**，不会独立证明 rowsHash/rowCount 对真实行内容正确；`INSERTED` 不能作为 Fulfillment/ACK、Store/Link、原组 closure 或历史回填批准。真库未迁 a0v_096/097/098、应用无 operator grant；原 12 Run 和全机 Fleet/Owner 授权缺口不变。W5c9h 单独规划行级语义 proof/拒绝门，先隔离负例与可取得的独立源证据，不能反推真实扫描/商城源读取权限。
