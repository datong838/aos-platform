# 已提交 preparation 的恢复与 Schema 实证

2026-09-12。安装 3d267738-ba0a-49ef-812b-d6b72d3374fd 已 applied@4，apply a24af9ea-e390-4292-94fc-531890c6bf1a succeeded；verify b440f801-7825-420b-8b48-38a054c96131 accepted。独立 Host 在 verify 报 LookupError 后关闭；三资源 released/observed=true、无绑定。extension_schema_installation 为空，现有 require_installed 对缺失回执抛出 LookupError。不能将安装或测试标为 active。

下一波六步：

1. 读取签名包 Schema requirement/compatibility，核对平台迁移祖先和 requiredRelations 的真实存在；通过已有 schema_registry.apply_once 维护入口登记 exact Receipt，回放不写，不伪造 migration 完成。
2. 产品恢复契约：applied 但没有绑定且全部资源已释放时，允许当前授权控制者通过幂等命令追加 preparation reset 到 approved；在同一事务终结尚未提交的 verify。保留原 succeeded apply、immutable 安装修订及资源记录。禁止重开原资源身份或重写原 apply。
3. 完善方案后增加不可变 revision transition、独立 evidence 类型、当前权限/CAS/资源清洁/未决操作检查。跨租户、绑定存在、不确定释放、verify 已提交均拒绝。
4. 真实隔离库执行一次 reset，重复命令回放，然后新 apply 使用新的 Operation 和资源 generation。
5. 同一独立 Host 完成 apply/verify，确认 active/ready、配置前 disabled/fenced。
6. 归档并进入四来源配置、enable 与经营首链。

风险：旧 PreparationOwner 只有最多 300 秒寿命，恢复不等于长期持续可运行；enable 后宿主持续性仍需单独观察与改进。严格保持真实业务目标，不能因安装过绿而宣称八工作台已完成。

## 第 1 步实证

维护脚本 `scripts/a0v_ecommerce_schema_receipts.py` 完成签名校验、平台迁移祖先检查和各包 13 个物理关系检查。首次因检查时间早于加载证据而拒绝，事务没有写入；调整加载顺序后，三包 exact Schema Receipt 首次 recorded=true，重复执行全部 recorded=false。证据见同目录 ecommerce-1.6-schema-apply.json / ecommerce-1.6-schema-replay.json。三个物理条件测试通过；未执行 DDL、业务调用或安装状态变更。

## 恢复实现文件与验收约束

- `services/aos-api/aos_api/extension_runtime/preparation_reset.py`：当前权限、Installation CAS、无绑定、所有资源已释放；只收束 runtime-verify 的未提交阶段。必须拒绝 committing/succeeded 以及其他未决操作。
- `services/aos-api/aos_api/asset_registry/{composition_contracts,installation_evidence,installation_store}.py`：明确 preparation_reset 证据和 applied→approved 追加修订；继承原 decision，保留全部历史。
- `services/aos-api/alembic/versions/a0v_017_*.py`：数据库同样强制清洁检查和 decision 继承，不依赖脚本绕过。
- 对应 runtime 与 installation 测试：覆盖权限、租户、CAS、绑定、释放不明、已提交 verify 拒绝及合法恢复和幂等回放。

数据库迁移前备份。回滚采用停止新控制操作和保留历史，不删除已追加修订。原安装未恢复前不发第二次 apply。
