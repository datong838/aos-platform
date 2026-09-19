# AP direct successor 与冻结十二源恢复验证

## 结论

AP installation `733a1366-c61d-4800-9310-4d5d8057ced7` / generation
`0640c5ce-f384-457c-94d2-3355faa39f46` 已由正式 lifecycle 建立、注册为 AO 的唯一 direct
successor，并完成九条 extension route 的正式 cutover。冻结十二源 definition 已转移到 AP，recovery
已续为 revision20；全过程 sourceReads=0，未调用 `run_definition`，未产生 Store attempt。

本波在执行前主动保持 qcursor 停止。原因是 AO 已连续出现 IngressJournalConflict 与 Lease expiry，若在根因未查明时
直接启动 AP，会违反“未知结果不得重发”和失败恢复边界。AP 当前是已安装、已路由、已配置但未获执行授权的安全待命态，
不代表 recoverable Store、经营参谋自然首链或八工作台真实业务完成。

## 安装与 direct successor

- AP lock：revision1，`sha256:048a98bc7dca660c371b1f7cda9530ba73aa691b5f92d3f9f9b6b5b67868d56f`；
- configuration：`ac60a83a-dd28-4544-b014-f62f8d00489d`，
  `sha256:2a6c90d936b5890144b3c09872ca61a9a34f0633f601552d3d68ac34726ec953`；
- 安装终态：head etag5 active，binding revision4 / epoch3，enabled、ready、unfenced，3 个资源均 live，
  `dev-org/dev-project` canary=0；
- predecessor：只消费 AO detach Receipt `c98d7a33-2653-42a8-86f1-05f26c09217e` /
  `sha256:b4e2969a445b0459dd0e43376d600ab87a515374774e3434d31a28eb014c29f9`；
- successor registration Receipt：`de0ff69f-380b-4bc5-97dd-9f6f5d2276cb`，request hash
  `sha256:bad3f1b38b154cd847c8b6961811860023142cb6a9f4887d1007a85cb35e478f`，注册时 executable=false。

## 正式 cutover

cutover operation `c9a8a6a8-517f-47aa-b8c2-86b95a77f14b` 完成
`approve → prepare → pause → commit → validate → resume`。九条 route 从 legacy revision98 / group125
切换为 AP extension revision99 / group126，目标 Runtime revision6，claim 已恢复，期间不存在 claimed、unknown 或 running attempt。

关键 Receipt：

- prepare：`89569f98-8787-4371-a9df-ecf55bd6f6d2`；
- pause：`cce9ea6d-935b-4f5b-898f-8b16bc8efd5e`；
- commit：`0e9e4acc-8dc3-4605-aba5-fdbc85396a6d`；
- validate：`b232e94e-3479-448b-93e6-6c506d9ae47b`；
- resume：`77960574-da23-4259-a7e3-6a260d12fa38`。

## 冻结十二源恢复

- snapshot group：`c5ff1926-45b0-56de-b6b3-07d5b7d053a1`；
- input manifest：`sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`；
- definition 先由 AO revision60 disabled 转移为 AP revision61 disabled，再由 recovery 续为 revision62 enabled，
  hash `sha256:450ebd60324b2f638da8638711736892da5825b5f57fdd3ed9a01c13cca9a24b`；
- recovery revision20，hash
  `sha256:f5dc9958948611c42d4083305b0a6e5c58e97add3c97d76a4cede4504bb62d1f`，
  request hash `sha256:dfd54537fc1240a95b2ffbaabd1237908357d1ed7e4b3dc18f6aea20b55e7db7`；
- 十二个 Run 保持 running，原 dataset receipts、relationship 与 link command 不变；全部恢复动作 sourceReads=0；
- enable 读回为 configurationState=enabled、executionAuthorized=false、routingStatus=original_group_pending；
- qcursor LaunchAgent 未加载，18181 无监听；Runtime Host `com.aos.a0v-runtime-u` PID 59258 正常运行。

## 测试、一致性与已知执行记录

- AP replacement/successor/cutover/saved recovery 专项：4 passed；
- AP + AO retirement/guard/router/recovery + AL/AM retirement 累计回归：61 passed；
- `py_compile` 与 `git diff --check` 通过；
- 一次专项测试使用了错误短路径，在收集前退出、0 tests；随后用实际 extension_runtime 路径重跑全绿；
- 一次 0600 回执检查猜错状态根目录，只读 `stat` 失败；随后从脚本常量解析实际目录并确认回执存在；
- schedule-ingest 首次在 18181 未启动时连接拒绝，发生于任何写入前；临时启动 API 完成十二项确认后再次停止，未扩大执行授权。

下一波先完成 AP 执行前 Ingress Journal 冲突根因分析与确定性修复。根因和未知提交边界验证通过前，不启动
qcursor、不自然领取 AP attempt；修复完成后才恢复唯一合法执行并进入终态观察。
