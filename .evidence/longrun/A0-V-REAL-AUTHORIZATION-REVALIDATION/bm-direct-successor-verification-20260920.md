# BM 直系后继材料门验证

## 结论

`BM_DIRECT_SUCCESSOR_MATERIAL_BLOCKED_FAIL_CLOSED`。

BL exact detach preflight 为 GREEN，但 canonical trust root与 Runtime Host三角色 credential file在本机
重启前后均已消失，且不存在可证明 exact 的恢复副本。BM create未调用、BM installation未产生，当前边界
安全冻结；禁止生成新 trust root、重签旧版本或绕过 release revalidation。

## exact predecessor 回读

- BL installation：`ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc`，lock
  `sha256:47af46b5658b7952f9d3068466ba06c6203e51fef899c5d661026230893b334e`；
- generation：`116d12fc-93bc-4071-a973-fdc6830ea8b1`，Binding rev8/epoch4，
  disabled/fenced/unknown；
- disable operation `7e82992b-0f1b-429f-bcda-36d416ff9cdb` succeeded；detach Receipt
  `3a50db9a-2dec-4543-b37a-701a8e12ee36` / hash
  `sha256:265c6dcf811b6df90e5402fc7f1bc53aad22d8f49d29ec7caffe90f779a40f15`；
- 三资源 released；九路 legacy rev164/group191；definition rev118 disabled；
- `replacement-bm/preflight-result.json` mode `0600`，outcome
  `BM_REPLACEMENT_PREFLIGHT_GREEN`，externalEffects=0。

## 材料恢复审计

1. 原 canonical state、event-complete signed bundle目录与
   `.aos-recovery-20260912/state/ecommerce-runtime-host/runtime-host-identities.json` 均不存在；Trash无副本。
2. APFS数据卷与Time Machine无可用本地快照。
3. 数据库仍保留四个 published manifest、签名对象、174条 artifact索引及 signature verification证据；
   证据只含 keyId与trust-root revision，不含 publicKey或artifact实体，不能独立重建信任根。
4. 原 keyId为 `a0v-local-ecommerce-canonical-v1`，trust-root revision为
   `sha256:fc8d449ed6b5dea8b2b933ee0f573e794c9ebe86f540d8b6aab23462f12219c7`；
   Git历史、项目文件、Colima BuildKit content cache、overlay/image metadata均无完整trust-root JSON。
5. 三个 runtime signed bundle仍可由从未启动的已验证OCI镜像精确恢复：
   - growth 1.10.0：image `2aa6dd6b1e63`；
   - core 1.4.0：image `4f056527d01d`；
   - niushop 1.23.0：image `3cb783e202e7`。
   但缺少原public key时无法完成签名验证，因此未写正式恢复目录。
6. Ed25519签名与原文不能作为原public key的可验证恢复源；任何新生成key都会改变root revision并突破
   已发布版本权威，故明确拒绝。

## 零副作用与运行边界

- 最新 installation仍为BL；不存在BM create-result或BM installation；BM state仅有preflight result。
- extension runtime attempt：43 total / 0 running / 43 terminal；runtime pending=0。
- exact Store Receipt=0，`ecom_link=0`，projection pending=0，`dev-org/dev-project` route canary=0。
- 18181无监听；AOS Runtime Host、snapshot worker、Cron均未启动；未调用 `run_definition`，未读取商城源数据。
- 临时OCI检查容器仅create/cp/rm，从未start；检查结束后无残留。

## 测试与方案一致性

- BM/BL replacement专项：2 passed；
- BM wrapper只覆盖方案冻结的exact BL常量，未修改共享实现；代码中无 `run_definition`；
- 方案第2步材料恢复门未GREEN，按停止条件未进入create、Host lifecycle或cutover，行为与方案自洽。

## 恢复条件

只有提供原 `trust-roots.json`（必须回读上述revision）后，才能继续恢复三个OCI bundle并评估三角色
credential的正式轮换方案。仅有私钥路径、keyId、签名或revision均不足以授权继续。
