# BE 直系后继与单 Host 激活方案

## 父权威

BD installation `c2d6ef97-30ec-4980-9421-54a899607853` / generation
`f5e01f1d-e6c5-425a-9145-6f7a82ec65e5` 已由唯一 disable operation
`f5f52787-c6f1-468b-9e7e-878113942c65` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev140/group167，detach lifecycle 为 exact `fence → detach` 两张 Receipt；detach Receipt
`c896fec3-dbe2-46fe-be60-3cc249b4b4ed` / hash
`sha256:8845a269e68dd54bfa89ca1e8a1f5785e199fb80985f86d08f93b5b570581495`。definition rev94 disabled，
唯一 terminal attempt 已冻结，Store/link/projection/canary 全零。

BE 只能从该 exact BD detach authority 创建，不复用 BD identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_be_replacement_recovery.py`：复用既有 replacement Owner，锁定 BD exact detach、lock、
   rev140/group167、definition rev94，创建全新 BE installation/generation/configuration。
2. 创建完成后，新增 `scripts/a0v_be_successor_business.py` 与 `scripts/a0v_be_successor_cutover.py`：只在 BE
   enable 正式 succeeded 后 register/cutover，目标九路 extension rev141/group168。
3. 沿用当前唯一前台 Runtime Host；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或 snapshot
   worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BD detach、legacy140/group167、definition94 disabled、attempt0 与业务零副作用；创建 BE
   后固定新 identity。
2. 保持唯一 Host，执行 prepare；只读等待 apply 正式 succeeded 后才执行唯一 verify；verify succeeded 后连续
   stage/configure/enable，避免健康观察过期。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown
   立即停止，不重发 enable。
4. enable 成功后 register，并串行 approve/prepare/pause/commit/validate/resume；终态九路 extension
   rev141/group168，definition 仍 rev94 disabled。
5. 记录至少 12 次新增健康续租，verification 落盘、测试与精确提交后，才进入 BE saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
