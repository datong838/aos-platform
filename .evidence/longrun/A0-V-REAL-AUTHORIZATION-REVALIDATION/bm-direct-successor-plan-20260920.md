# BM 直系后继与受保护运行材料恢复方案

## 父权威与目标

BL installation `ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation
`116d12fc-93bc-4071-a973-fdc6830ea8b1` 已由唯一 disable operation
`7e82992b-0f1b-429f-bcda-36d416ff9cdb` 正式退休：Binding rev8/epoch4
disabled/fenced/unknown，三资源 released，九路 legacy rev164/group191，detach Receipt
`3a50db9a-2dec-4543-b37a-701a8e12ee36` / hash
`sha256:265c6dcf811b6df90e5402fc7f1bc53aad22d8f49d29ec7caffe90f779a40f15`。
definition rev118 disabled；唯一 attempt
`06352972-8c80-4291-aece-2474209e6a76` 已为正式 abandoned terminal，十二 saved Run/Receipt
仍保留，Store/link/projection/canary 全零。

BM 只能从该 exact BL detach authority 创建，全新 installation/generation/configuration；不得复用
BL identity、attempt、snapshot worker或任何旧 intent。

## 已发现的材料丢失与恢复边界

重启前运行所依赖的受保护目录已消失：原 canonical `TRUST_STATE`、event-complete signed bundle
目录、Runtime Host 三角色 credential file 均不可读；垃圾桶无副本。canonical create 在组合解析前即
强制读取 `TRUST_STATE/signing/trust-roots.json`，因此缺失状态下禁止调用 create。

恢复只允许满足以下全部条件：

1. 从既有不可变权威（数据库发布记录、历史 Receipt/verification、已验证 OCI image或系统快照）恢复
   exact 字节，并以既有 digest/revision/signature 做交叉回读；
2. 不生成新 trust root，不重签 bundle，不从日志输出或提交任何 secret；
3. credential 若需轮换，必须另立方案，使用既有三角色与正式最小授权过程；不得猜测、复用 owner
   密码或把凭据写入仓库；
4. 任一 trust root/public key、bundle artifact、signature、credential identity 无法证明 exact 时，BM
   停在 preflight/material-blocked，零 successor 写入。

## 文件与最小代码范围

1. `scripts/a0v_bm_replacement_recovery.py`：复用既有 replacement Owner，只锁定 BL exact detach、
   lock、rev164/group191、definition rev118，创建全新 BM identity；不改共享实现。
2. `services/aos-api/tests/extension_runtime/test_a0v_bm_replacement_recovery.py`：固定上述常量、
   preflight fail-closed与禁止 `run_definition`。
3. 恢复材料若需要新增确定性工具，必须先增补本方案，工具只能读回/校验或按正式接口恢复，不得
   绕过发布、签名、凭据与三平面权限门。

## 串行步骤

1. **exact preflight**：回读 BL head/lock、Binding rev8/epoch4、三资源 released、disable succeeded、
   fence+detach Receipt、九路 legacy rev164/group191、definition rev118 disabled、唯一 terminal attempt
   与业务零副作用；落不可变 preflight result。
2. **材料恢复门**：只读枚举可恢复来源，逐字节恢复并校验 canonical trust root、event-complete
   signed bundle、三角色 credential identity；未全 GREEN 不进入第 3 步。
3. **create BM**：材料门 GREEN 后才写 backup/create-intent并调用正式
   `create_approved_first_installation`；结果必须 approved且 identity全新。
4. **单 Host lifecycle**：Runtime Host=0 起步，只启动一个正式 Host，读回第二 Host=0；依次
   prepare → verify → stage → configure → enable，任一 unknown/stale立即停止。
5. **register/cutover**：enable正式 succeeded且 Binding rev4/epoch3 ready/enabled/unfenced、三资源
   live后，才 register并串行 approve/prepare/pause/commit/validate/resume；目标九路 extension
   rev165/group192，definition保持 rev118 disabled。
6. **健康与封板**：至少12次新增健康续租；verification落盘、专项测试与精确提交后，才进入 BM
   saved-snapshot recovery。

## 停止条件

- 材料来源或 digest/revision/signature 不完整；credential无法由正式受控流程恢复；
- predecessor、route、definition、Receipt、attempt、业务零副作用任一不精确；
- create/lifecycle/register/cutover出现 unknown、部分提交或读回不一致；
- 发现第二 Host、Cron、snapshot worker、手工 `run_definition`、商城源读取或 `dev-org` 写入。

任何停止都先落 verification，冻结边界并提交；不重发未知操作。全程不读商城源数据，230 L0
继续挂起，不 push、不动其他分支。
