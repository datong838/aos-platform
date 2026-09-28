# W5CB4 E17-l｜当前签名安装与三身份目标库只读交叉预检方案（2026-09-28）

## 上位与当前事实

- 231-2/231-3 要求签名制品、当前安装、三身份、精确 Host assignment/Owner 与四源配置共同准入。E17-i 当前签名/安装预检 GREEN，但受保护的当前三身份凭据、固定 OCI、Host identity/assignment 和 active 配置未齐；E17-k 发现旧三身份可“彼此同库”，却没有与当前签名安装的库交叉绑定。
- 当前库 `aos_current_preview_20260927@a0v_109` 只读；旧身份文件实际指向 `aos_meta_head`。本波只做无作用预检，不调用 Host selector/worker/Provider，不写库。

## 文件级拟实施

1. 新增 `scripts/a0v_current_runtime_host_preflight.py`，复用 `a0v_current_preview_http.preflight(signed_receipt)` 的签名树/Registry/当前安装/目标库只读核验。输入要求显式 `--signed-receipt` 和绝对、0600、非 symlink 的 `--credential-file`；不读取默认历史文件或 `.env` 中凭据。
2. 在读取受保护三身份文件后先对 DSN 的 `dbname` 做快速拒绝；随后各以只读事务实际连接，复用 `probe_runtime_database_identity` 和 `require_isolated_runtime_identities` 核同一物理数据库、互异、非特权/非关系 Owner/组隔离；目标数据库 authority 必须与当前签名安装预检的实际数据库相等，不能由命令行任意数据库名自证。只读核精确 `org-org/dev-project` 的 `assigned` Host assignment 指向已启用且与 Directory 登录角色及 OID 一致的 Host identity，并读取八类配置候选。当前 `bundle_installation.created_by` 仅是安装创建者，不能当作正式运行 Owner；安装生命周期 Owner 必须由后续真正准入门证明。任一缺项返回固定无密钥 reasonCode。
3. `scripts/a0v_current_preview_http.py` 的签名安装预检连接先显式设只读；修复 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py` 中旧 `a0v_107` 断言。新增专项测试（`services/aos-api/tests/extension_runtime/test_a0v_current_runtime_host_preflight.py`）：先 RED 覆盖无凭据、旧库 DSN、三身份混库/同角色/特权、签名不符、assignment/Host identity/配置缺失、未知结果不启 Host；GREEN 用受控 fake 连接/隔离库验证纯检查。再相关累计、语法/差异与必要时当前真实库**只读**运行（缺正式凭据预期 SAFE_BLOCKED）。
4. verification 登记证据与限制；m1 精确提交，D-waves/01/06/Prime 同步。不会把预检通过单独当 Host 授权；正式批准链、签名、业务配置、禁入/恢复仍由组合门消费。

## 施工前复核点

已核对 `a0v_current_preview_http.preflight` 返回连接参数与 `a0v_109` 当前库；`probe_runtime_database_identity` 的 authority 取数据库服务端地址、服务端端口和 DB 名，能与同库 root 只读查询比较。`ar1_003` 合同为 assignment `state='assigned'`、host_id 关联 enabled identity，identity 的 database_role/OID 与 Directory 登录身份相符；`runtime_configuration_candidates.read_candidates` 精确读取八项。预检不将候选存在误判为已绑定配置，也不把静态 Host identity 误判为活跃安装 Owner。若实现需要修改当前库或复制凭据，缩回只读方案，不越权。
