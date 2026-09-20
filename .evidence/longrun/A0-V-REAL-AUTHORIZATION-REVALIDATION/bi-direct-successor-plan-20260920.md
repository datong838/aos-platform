# BI 直系后继与单 Host 激活方案

## 父权威

BH installation `7b7d4319-e639-48c9-971b-0efbfb9251ef` / generation
`f6023b7c-ca6f-49ac-b9ff-4dcbca62745c` 已由唯一 disable operation
`33167268-e7e6-42fc-90f9-e2cb83e6f932` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev152/group179，detach Receipt `8609e798-2f61-43df-9838-cad7da02c230` / hash
`sha256:25b34bd970571e9d9f402380fa483433f6343a441f969e6f6b5c044e60975ea9`。definition rev106 disabled，
唯一 terminal attempt 已冻结，Store/link/projection/canary 全零。

BI 只能从该 exact BH detach authority 创建，不复用 BH identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bi_replacement_recovery.py`：复用既有 replacement Owner，锁定 BH exact detach、lock、
   rev152/group179、definition rev106，创建全新 BI installation/generation/configuration。
2. 创建完成后新增 BI successor business/cutover/health wrapper；只在 enable 正式 succeeded 后 register/cutover，
   目标九路 extension rev153/group180。
3. 沿用当前唯一前台 Runtime Host PID 10991；启动/执行前证明第二 Host=0，不使用 KeepAlive，
   不启动 Cron 或 snapshot worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BH detach、legacy152/group179、definition106 disabled、唯一 terminal attempt 与业务零副作用；
   创建 BI 后固定新 identity。
2. 保持唯一 Host，执行 prepare；apply 正式 succeeded 后才执行唯一 verify；随后连续 stage/configure/enable。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown 停止。
4. register 后串行 approve/prepare/pause/commit/validate/resume；终态九路 extension rev153/group180，definition
   仍 rev106 disabled。
5. 记录至少12次新增健康续租，verification、测试与精确提交后才进入 BI saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
