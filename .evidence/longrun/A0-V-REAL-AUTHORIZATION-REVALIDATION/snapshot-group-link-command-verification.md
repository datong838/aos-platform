### SC4-5h3 关系命令准备验证

新增 a0v047 及 PipelineSnapshotGroupLinkCommandJournal。仅从原 current assessment 生成纯关系命令，先重核所有原对象投影及原不可变关系准备；服务端 stream 使用 installation_id 和 policy path，幂等键绑定 group/assessment。完整命令及 CAS 检查点不可变保存，后续重放不再读检查点重建；空组保存明确null，不造 Receipt。

35项隔离PG组合通过49.96秒，其中新13项，原关系journal15项，组对象7项。验证原命令应用后检查点已前进仍精确重放；原准备缺失、未应用对象、权限撤销、回滚、租户隔离及不可变约束；保存后禁入即使外层捕获仍由savepoint清除；形状和hash合法但候选关系被改的记录被当前Owner拒绝；真实空输入无权威Receipt。首次实现把安装引用误按普通resource_id读取，按原CurrentInstallationRef.installation_id纠正，没有修改引用协议。

AR2扫描1921/187/93、五类错误为空。迁移只运行隔离库，主库仍原基线，真实1162候选未应用。本波准备不是应用授权或Fulfillment。下一项：独立提交确认后重新进入当前Owner，严格关系应用；复用原有精确事件投影流程而非全租户扫队列，最终重新核对完整对象及关系当前Receipt/投影。旧关系清退、客户引用缺口、业务Readiness仍待完成。
