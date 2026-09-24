# W5c3o 已卸载 DS 的第三继任者登记方案（2026-09-24）

## 纠偏与现行依据

W5c3n `02b5a348` 的清点结果正确，但其“必须新增 Owner/SQL”结论不完整：`a0v_073_uninstalled_successor_registration.py` 早已将原 `extension_dispatch_successor_register_a0v_056` 收紧式扩展为允许 **正式卸载且 activeRevision null** 的旧绑定 `uninstalled/stopped`，前提仍是原 detach/disable/九路快照/资源/零在途全部满足。2026-09-16 的 L 波已在克隆及主库验证此路径。不能仅凭迁移文件存在就认定当前库函数已加载，须读回当前数据库函数定义/迁移链并用原 Owner 的正式预检。

W5c3m 第三安装 `407059df-6f1f-4927-acd7-8e388692838e` active/etag5、generation `7571af17-e2bb-4437-9f04-75812bae56c0` binding rev4/epoch3 enabled/ready/fence off、config rev1/hash `sha256:f21169b03b4aba5dec2e6bbaa8ee8921e5ed833eee558f051b6e564aa068e359`、Host PID17302/三 held 资源。DS 正式卸载，latest detach `d64e1b84-bdf9-4d15-b740-16673fcd651a`/hash `sha256:85f803080a8d348da90040540c5cc1d3fef48bbee857db3598265eaf0a37dd9c`，group `6a402d31-83ad-546c-807f-508c87498ce1` rev365、九路 route rev338 legacy/fenced。12 schedule off，新 selection/control/definition0。

## 本波唯一写入

仅使用既有 `FirstDispatchRegistrationService.register_successor` 登记新安装，生成非执行 Receipt；不切九路、不开放 12 调度、不读取商城源、不手工业务 Run。新增精确 W5c3o 包装脚本及定向测试，不修改领域 Owner/SQL。全新键 `a0v-w5c3o-third-successor-registration-20260924-v1`，私有 0600 intent/result；未知结果只按 installation/key/actor 读回，绝不重发。

## 串行步骤

1. 只读复核 W5c3m audit、预算/四来源当前、Host/Job/资源、DS uninstalled/activeRevision null、disable/detach Receipt/hash、九路 exact snapshot、running/unresolved/pending/canary0、新键 Receipt0。独立确认主库 a0v073 兼容分支仍存在，且 `a0v_056` 其他门禁未被绕过。
2. 生成严格 `SuccessorDispatchRegistrationRequest` preview：目标安装/lock/overlay/config/binding 精确；expected group rev365；前任 detach Receipt 精确。使用原 service 的 read-only current-authority/签名 qualification 校验；定向正反测试。
3. 冻结 intent 后只发一次原 Owner 注册。首次异常或提交边界未知，停止写，按原 Owner `read_successor_receipt` 与 DB 新键只读对账；不得换键或重发。
4. 独立核唯一非执行 registration Receipt、requestHash、九路仍 9/9 legacy/fenced rev365、Host/资源/调度/业务计数不变；verification 后 m1 commit。下一波才独立计划 cutover approve→prepare→pause→commit→validate→resume。

## 停止条件

迁移函数体不含 a0v073 正式卸载分支、DS 无正式卸载、旧快照/Receipt/hash 不匹配、九路或 runtime/Host/预算漂移、任何未结操作/unknown/canary/业务 Run、Owner 权限拒绝或提交边界未知，一律冻结；不补写数据库、不手工 run_definition。
