# AW 直继实例方案

## 父权威与目标

AV 已通过 disable operation `badb43f6-cb04-48ae-88ac-07f09122e872` 正式退休。Binding 终态为
rev8/epoch4 disabled/fenced，3/3 resources released，九路回 legacy rev119/group146；exact detach Receipt
`eed47855-2a96-4709-be2b-8283422a180a`，hash
`sha256:9b60c491ad0476127c95740ab7f32276de6bb1ebeaf063326e70fe5a28f757ca`。

definition 保持 rev76 disabled，AV 唯一 attempt 保持 abandoned；12 Runs/Receipt 保留，Store/ecom/
projection/in-flight/canary 全零。AW 只能从上述 exact detach Receipt 创建，不得复用 AV identity。

## 文件级清单

1. 对已验证 AV replacement/successor/cutover/health 执行器仅抽取 predecessor route/group、definition 与
   successor identity 等波次常量，AV 默认合同不变。
2. AW replacement wrapper：固定 AV 退休身份、operation、Receipt/hash、legacy rev119/group146 和
   definition rev76 disabled；Owner 签发 AW installation/generation/configuration，未知结果不重发。
3. AW successor/cutover wrapper：登记 exact AW 后继，六阶段 cutover 到 extension rev120/group147，
   `externalEffectsAllowed=false`。
4. AW health wrapper：唯一 Runtime Host 上只读观察至少 12 次新增续租；definition rev76 disabled、
   AW attempt=0、三资源健康、零 in-flight/canary 始终保持。
5. 对应专项测试与 verification 固定所有实际身份、Receipt、revision 和禁止 `run_definition`。

## 串行步骤与停止条件

1. 只读复核 AV exact detach、legacy rev119/group146、definition76 disabled 和零副作用。
2. 依次执行 AW preflight/create/prepare/verify/stage/configure/enable，只使用 Owner 实际签发身份。
3. 登记前必须确认 AW Binding rev4/epoch3 ready、三资源 pending、四项 operation succeeded、
   全租户 in-flight=0、definition76 disabled。
4. successor registration 后执行 approve/prepare/pause/commit/validate/resume；终态必须 Binding
   rev6/epoch3 ready、九路 extension rev120/group147、definition76 disabled、AW attempt=0。
5. 唯一 Runtime Host 必须读回 1800 秒上限；至少 12 次新增续租后才落盘 verification 并提交。

任一 identity/revision/hash/Receipt 漂移、非零 attempt/canary、双 Runtime Host 或未知结果都立即
fail closed；不读取商城源数据，不 push，不改其他分支，230 L0 继续挂起。
