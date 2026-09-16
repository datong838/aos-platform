# Y3c-3b 固定准入接入原保存输入通道

## 实施与验证结果

2026-09-16：Red构造器尚无固定recovery参数（1 failed，10.59s）。首项双窗口读取15.56秒通过；恢复Input/原context/原执行守卫组合32 passed，72.20s；原native input独立4 passed，20.86s；原单路SourceClaim、Input、实际Store投影及controlled runtime回归59 passed，21.82s。投影序列化专门具名seam1 passed，16.93s，证明journal使用新授权ref而payload保留原claim ref；该seam不冒充完整恢复Store验收。日志`/tmp/aos-recovery-input-final.log`、`/tmp/aos-recovery-input-native.log`、`/tmp/aos-recovery-input-legacy.log`、`/tmp/aos-recovery-projection-refs.log`。diff检查通过。

恢复原数据观察时间确实早于新notBefore，仍保留原manifest/claimHash/old controlRef，当前group用新窗口；新source reserve/prepare/group claim全部拒绝，普通实例不能借用续期控制，错组/部分组/回调disable拒绝且回滚。只隔离fixture一次源调用，未创建新Run/SourceClaim。主库061及真实首链未变；下一波C3c原Completion真实Store恢复运行，再C4/C5。

前置0096e260当前恢复准入与C3双窗口方案。精确文件：修改aos_api/pipeline_source_claim_owner.py、pipeline_snapshot_group_input_owner.py、pipeline_snapshot_group_projection_owner.py；新增tests/extension_runtime/test_snapshot_recovery_input_pg.py。暂不修改原GroupClaimOwner及Runtime/Completion，不执行Store。

SourceClaimOwner增加可选的固定SnapshotGroupRecoveryAuthority实例与十二新控制/原Run绑定；只能精确类和共享controls构造，不接受allow布尔。恢复实例reserve和单路prepare/新group准入明确拒绝；原read_current/read_saved_current只在该固定模式中强制走已有saved-recovery比对，当前控制仍经原ControlOwner，原SourceClaim返回原ref。普通实例默认路径不变。每次单成员守卫先确认该(ref,run)在固定配对内，再完整重验C3a权威；本波不加权限缓存。

InputOwner仅对固定恢复实例进入专用恢复分支，由C3a同步包围，使用原事实manifest/parent/采样时间和原claimHash，逐成员调用原SourceClaim保存或完成读取，前后重读claim。source.group仍是当前执行组，旧观察窗口已由C2b核验，不再将采样时间套进新窗口。增加可选recovery_ref字段仅用于当前授权追踪，不纳入原业务投影/评估payload。GroupClaimOwner普通路径不变，恢复分支不按新draft重算原source claim request_hash。

Projection payload的controlRef统一来自source.claim.members的原控制记录，ControlledIngressJournal仍用source.group中的当前授权ref。普通路径两者相同，恢复路径保留原证据身份，避免续期改变既有projectionHash/后继幂等键。没有重写旧凭据，也没有伪造读完成。

验证正式原input→C2c审批→固定SourceClaim/Input读取：保留原claim/ref/hash/采样时间、当前group新窗口；恢复reserve/单路prepare/不完整组拒绝，普通实例不能绕过saved-only；回调中disable/当前控制变化拒绝及回滚；原普通Input/Claim/context/guard回归。原projection事实控制选择加针对性验证。随后C3c/C4恢复Runtime/原失败Run，C5实际Store整链压力验证；本波成功不能宣称真实恢复闭环。
