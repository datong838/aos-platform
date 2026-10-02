# E17-a2b2｜当前安装版本感知发行与 OCI 只读证据视图

## 上位合同/当前事实

231-2 要求当前可信 release、签名字节、exact lock 与实际 OCI digest 同核；231-3 要求 active 安装指针与 ready binding 的 revision、generation、lock 同代，且 enabled/fence/epoch 的执行许可单独计算。E17-a1 已有同一只读事务的当前发行读者，但没有 binding/OCI；E17-a2a/b1 在隔离 PG+OCI 证明 Growth1.13 正链及失效拒绝。当前实例仍四旧包 approved/binding0、正式 OIDC/三身份/信任根/八配置/Owner 缺失，本波不能启用当前 Host/API 正式模式。

## 精确文件和 RED

1. `services/aos-api/aos_api/extension_runtime/current_installation_release_evidence.py`：抽出原读者的**同一事务内**私有解析函数，旧公开读者行为及 `EVIDENCE_ONLY_NO_START` 不变。新增只读 `read_current_runtime_image_evidence`：要求 active=current、唯一同代 ready binding/lock hash、原 resource lease 的 generation/package/content hash 精确集合；复用 ManifestLoader 的 allowlisted 已签 artifact 读取、原 `admit_runtime_artifact` 与实际 OciDriver cache inspect，返回签名 image/config digest、schema head、ETag、binding generation/revision，但固定 `EVIDENCE_ONLY_NO_START`。不能用此结果直接解 Host。
2. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：在原 1.13 原生产者的 active+disabled/fenced binding 后，先 RED 新函数缺失；再正向核 exact 发行/OCI/同代代次，负向让错 generation 和停止后的非 ready binding 失败关闭。错 lock 与改动 artifact bytes 已由紧邻 E17-a2b1 原生产者/不可变触发器证明；旧 1.12 路径保持。更深的 epoch/Owner 执行门保留给正式 selector，不能以证据视图替代。
3. `services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py`：当前四旧包 approved/binding0 对新视图必须拒绝；现有四个只读读者测试不变。正式 API/Host selector 仍是下一波：本波输出证据，不新增启动权限、不把本地测试签名升格。

先 RED、再最小实现，串行跑两套 PG 迁移避免共享 role 相撞；专项、旧 1.12、相邻读者/启动门、`py_compile`、diff、浏览器禁入与容器残留复核。当前真库只读，不读商城源、不重放旧 Run、不手工 run_definition、不碰 230 L0、不 push。完成后记录版本感知视图还缺的外部信任/身份/配置/Owner，以及正式受限 API/Host 接线具体文件。
