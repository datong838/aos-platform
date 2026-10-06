# S13 原账户/basis/request组合读取验收

基线6969642549867aa68660393cac593446f1e07e6b/AOS-001386；formal/publication Task同owner有效Lease至20:00+08，m1唯一施工。

## 实现

CAPACITY_SOURCE_COMBINATION_SQL组合实际原S11 request/S12 account,basis查询，引用参数固定映射，kind固定account/basis，scope/原maker/actual-stored-expected hash/mode/flags/shape门均保留。basis的账户四字段ref从实际account原行构建并完整相等；别名string逐字相等；Provider逐元素整个JSONB相等而非子集匹配；并发number/1..7位正整数CASE转换并约束1..1000000、basis不超申请。同maker原request行再次独立核。

原check_request保留Python四条判断，SQL组合门在neutral Evidence前实际调用；原模型、审批、Evidence/Provider及withdrawal/currentness顺序不变，原拒绝语义保留。无新增锁、schema/function/grant、迁移或正式发行入口；真库未操作。

## 本次验证

- combination-red.log：2 failed/9.44s，新常量缺失RED，未当业务拒绝证据。
- combination-green.log：2 passed/9.69s，早期版，最终新增maker及边界值由下项覆盖。
- combination-adjacent.log：最终六模块450 passed、7既有warnings、215.84s，实际进程exit0。覆盖原runtime申请/审批、Source审批、private边界、publication与Sourcecontracts。
- 专项实际私有SCRAM原三行/完整approved claims正向，错maker/tenant/三引用hash拒绝。Detached原三表副本16类故障全部同步重hash，account变化同步basis账户ref；request maker同时修改row/wrapper，避免hash/ref/shape遮蔽。包含完整Provider多字段等价而非jsonb子集、boolean/fraction/null/string/zero/negative/50位数字。保存点恢复及最终rollback。
- combination-review.md：现有route_supervisor独立只读审阅最终逻辑，无新重大问题，最终相邻由施工者回读。git diff --check通过。

## 限制与接续

完整SQL typed模型/原Owner/currentness/签名等S01–S20尚未全部组到prepare/commit，真正COMMIT TTL待决；本门不授供应商事实/真实Provider/共享占额/业务执行。下一步原typed接受域/规范化及S14–S19完整组合。basis-time-original-contract-probe.json已证明原时间接受域较签名文档宽，不能以严格等价名义偷换。原Task/Goal保持ACTIVE，不作完整Delivery或自然首链通过结论。
