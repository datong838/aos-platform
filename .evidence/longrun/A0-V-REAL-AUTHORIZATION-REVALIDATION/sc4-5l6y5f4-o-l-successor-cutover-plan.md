# Y5f4-O L 九路 successor 登记与原子切换方案

日期：2026-09-16

基线：m1 `1e6fe383`

## 权威输入

- L installation `19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3`，revision 5，lock `sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8`。
- generation `64742c68-5e71-485b-a3c8-edc20be3d101`，binding revision 4 / epoch 3 / enabled / unfenced / ready。
- configRef `e02eeab5-eabf-41b5-82ee-47229b938e2f@1`，hash `sha256:f98af03c9790f56b50a08d8d876a0b019390225d51577e8fdf0926f775bd1ff4`。
- J 最终 detach Receipt `15f04808-68e3-481f-9e20-9c6cf43a49a8`，hash `sha256:da0fbd2e59fc3176274eade80acbdd58f2bce8fdbf24b29843b334c76c0c0f98`。
- 九路当前全部为 legacy/fenced，route revision 20，group `6a402d31-83ad-546c-807f-508c87498ce1` revision 35；running/claimed/unknown=0，canary=0。

## 固定阶段

1. preview：精确校验 L head/binding/config、三份 live resource、四个 succeeded operation、J detach Receipt 完整性、九路 group 35 快照和零 inflight。
2. register：使用正式 SuccessorDispatchRegistrationService 生成 L 的不可变登记 Receipt；request 固定 expectedGroupRevision=35，未知结果只按 installation/key/actor 读回，绝不重发。
3. approve：登记 Receipt 读回一致后，建立 externalEffectsAllowed=false、fallbackAllowed=false 的独立 cutover policy 与正式审批。
4. prepare → pause → commit → validate → resume：逐阶段固定 intent/result 和精确上一阶段 Receipt；每个未知结果只读 activation history，不跨阶段重发。
5. readback：九路必须全部为 extension、L installation/generation/epoch，binding revision 单调增加，group revision 单调增加，零 inflight、零 canary、零业务自动 Run。

readback 使用独立的切换后验证器，不放宽 N 波次只接受 legacy/fenced 的历史门禁。验证器固定检查 L revision 5、binding revision 6、九路 route revision 21 / group revision 36、a0v073、schedule/policy/binding 均未启用、resume 后无新增 schedule run，并核对 Runtime Host 仍为唯一正租户进程；任一字段漂移即失败，不执行修复写入。

## 实际登记阻断与修订

首次 register 在任何 Receipt/路由写入前被 `a0v_056` 的 `predecessor must remain disabled` 拒绝。该门禁只认识 disabled/unknown predecessor，未覆盖正式 uninstall 后 binding 的 uninstalled/stopped 状态，与本波“真实卸载后重装”目标冲突。

新增 a0v073 收紧式兼容：保留原 disabled 分支，同时只在 detach Receipt 完整、disable operation succeeded、旧资源/inflight 清零、旧 binding disabled+fenced 且旧 installation 当前 revision 正式为 uninstalled、activeRevision 为空时，接受 uninstalled/stopped predecessor。其他 stopped、缺安装卸载证据或任一快照漂移仍拒绝。先在主库克隆验证表指纹和正反用例，再部署主库。

原 register intent 保留。迁移后只允许 `recover-register`：用同一 request/key 先确认 registration Receipt 不存在、九路仍为 group35 legacy/fenced、L 仍 ready；确认首次事务已回滚后才重试一次。未知结果仍只读，不得以新 key 重发。

## 停止条件

- 任一 L 身份、资源、配置、operation、detach Receipt/hash、route snapshot、group revision 或 canary 漂移，登记前停止。
- 任一阶段存在 intent 而结果未知，停止写入并读历史；不删除 intent、不使用新 key 掩盖未知结果。
- registration Receipt 未确定，禁止 approve；validate Receipt 未确定，禁止 resume。
- 本波不启动 schedule、event-control、商城上游写入或任何自然业务 Run。

## 文件范围

- `scripts/a0v_l_successor_business.py`
- `scripts/a0v_l_successor_cutover.py`
- `scripts/a0v_l_successor_cutover_verify.py`
- `services/aos-api/alembic/versions/a0v_073_uninstalled_successor_registration.py`
- a0v073 clone/main 部署执行器
- 两个对应的执行器测试
- 本方案与阶段证据

只复用现有 SuccessorDispatchRegistrationService、cutover service、审批 Owner 和当前数据库角色，不修改领域写模型。
