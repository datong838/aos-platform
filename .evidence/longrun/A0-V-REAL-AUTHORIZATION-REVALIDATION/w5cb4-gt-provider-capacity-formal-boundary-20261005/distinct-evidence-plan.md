# S15 三路独立 Evidence 私有消费验收

基线 AOS-001394 / m1@5541c55c。依231完整Source退出与publication/sql-approval-equivalence-plan S15；原 formal-boundary Task/Lease 范围内。

候选一：S15三路真实原Evidence依赖；候选二：完整发行prepare/sign/finalize，实际COMMIT时限仍待原合同裁决，先做不依赖该裁决的第一项。

仅修改 services/aos-api/tests/aip/test_provider_capacity_formal_boundary_pg.py；证据写本目录。原申请Evidence保留；通过原build建立独立账户与basis Evidence、原candidate Store及原独立checker批准，原JWT maker与新精确proposal/event构成原命令。真实private SCRAM消费者合法读取后，分别通过原revoke接口撤回申请/账户/basis任一路，新private读取必须拒绝。每例三distinct IDs，禁止一份共享Evidence冒充三路覆盖。完整正向实际COMMIT仍是后继，当前不授供应商能力、不迁移真库或重启、不改业务代码/数据。

先运行专项验证覆盖缺口或失败，失败诊断后最小修复；再formal/source action相邻回归，精确日志/复审/提交与AOS/Prime同步。无产品UI变化，不新增浏览器验收。Task不以本片段Delivery。

## 实际结果与下一缺口

专项首轮3 passed/14.23s，7既有warning。没有产品代码RED或修复，属于三独立来源消费反例覆盖。当前新三路均合法原build/原批准/真实SCRAM读取；逐路原revoke后拒绝，未引入mock或helper替代消费者。

静态跟读 S15：source_authority._evidence 和 evidence_fence.lock_capacity_evidence_refs 当前只读Bundle current/frozen/revoked；原 evidence_bundle_provenance.read_build_provenance 尚未被容量Source相关模块调用。故完整S15 build provenance/receipt合同尚缺直接单项反例，下一应以原private入口删除或单项漂移真实provenance/receipt证明拒绝（先RED），沿原读锁及原read_build_provenance复用，不能复制第二套哈希/批准实现；先确认其独立Scope与权限，无真实库动作。静态缺调用只作为候选缺口，未以此宣称实际可绕过。
