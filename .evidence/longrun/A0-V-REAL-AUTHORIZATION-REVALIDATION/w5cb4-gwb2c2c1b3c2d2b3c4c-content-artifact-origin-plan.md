# d2b3c4c 已接受方案内容产物来源保持方案

上位：231-5 §9 的双来源合同、BG00gw d2b3c4c。当前正式 G2 Skill Eval 来源仍是签名包中的 BLOCKED 占位；本波仅修复已存在的结果消费者在生成可读 Artifact 时丢失 `accepted-stage-v1` 来源种类的问题，不启 Provider/Host，不把受控测试产物当真实经营内容。

## 文件级计划

1. `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`：先在可销毁 PG 的受控结果消费链追加一个新来源变体；断言落库的内容 metadata 保留 `sourceKind=accepted-stage-v1` 和单个原 `Artifact`，摘要包含分支种类，可被增长包的 `ReadableContentArtifact` 精确解析。原四来源产物字节/摘要不变。旧夹具把迁移头固定为 `a0v_111`，当前代码已 `a0v_135`；先改为从 Alembic 脚本读取唯一代码头，再取得针对来源字段的有效 RED。
2. `services/aos-api/aos_api/ecommerce_content_result_consumer.py`：仅在新来源命令严格通过 `_strict_content_generate_command` 时，把来源种类加入将要哈希和落库的内容 payload。未知 `sourceKind`、错误原 Artifact 类型/数量拒绝；旧来源不新增字段。已有 Receipt-first、Usage、Budget settle 和幂等逻辑不改。
3. 跑专项/相邻 PG 与纯合同回归、语法/diff、适用时浏览器。该旧 PG 文件的 RETURN 正向用例已有登记的 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`，须在全量回归保留 RED 证据，并精确排除此一用例复核本波与旧 ACCEPT；不能改公共 Action 门或把旧测试批准当正式授权。核真实库只读、Host/worker/Provider关闭。提交 verification、m1 精确提交、AOS/Prime 和 D-waves 更新。

边界：此波不解除生成 `execute` 和 bundle `execute_content_capability` 的新来源禁入；未有持久原 Review Receipt/正式 G2、Host 身份与八配置，不会触当前实例的真实 Provider。下一段是结果消费者与原 Stage Owner/内容专属 Eval/人工评审同源复核。
