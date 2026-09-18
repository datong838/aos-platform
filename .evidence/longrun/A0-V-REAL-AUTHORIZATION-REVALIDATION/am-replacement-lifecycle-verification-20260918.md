# AM direct replacement 生命周期验证（2026-09-18）

## Rules

- AM 只能以 AL 的唯一 detach Receipt 作为 direct predecessor。
- 每一阶段依赖前一阶段不可变结果；未知 create/apply/verify/configure/enable 不得重发。
- 使用受信 signed bundle 树与既定四包版本，配置必须引用当前治理权威。
- 本波只完成安装与运行时就绪；九路 successor registration、保存输入迁移和自然执行另行受控完成。

## 第 1/6 步：前置与创建

前置精确匹配 AL binding rev8/epoch4 disabled+fenced、三资源 released、九路 legacy rev89/group116，以及 detach Receipt `bd92aa48-77b6-4c34-82f9-0ede171083b3`。创建 AM `fd28d180-db24-4568-a848-101fcd3aa3c5`，lock `sha256:f2bcef04d615b0c6a19b2a0465be392130eb6a85627135a8c58a1177901942cc`，状态 approved/etag3。

## 第 2/6 步：prepare/verify

runtime-apply operation `5c82fbd0-75db-4a4a-9868-3eefa065fa29` succeeded；runtime-verify operation `a7c308d9-5c03-4c12-8deb-8ae186783f64` succeeded。新 generation 为 `d6bc117e-d19d-4413-beb4-02884206e290`，安装进入 active/etag5。

## 第 3/6 步：stage

新 configuration `05602ff4-db16-4519-bb68-ed790307fa5b@1`，hash `sha256:3022b8a18ad1ae1cc8ad9911513bad1eee3c3e07dbc3c8e5c779fd710d58e320`。stage `authorized=true`，policy ref 精确为 `a0v-ecommerce-runtime-policy-v1@8`，未复用 AL configuration。

## 第 4/6 步：configure/enable

configure operation `f5a0b41c-83ab-467e-ac60-703cb818b2f6` succeeded；enable operation `c4e1c8e9-c0c4-4053-939e-39e0779f2230` succeeded。

## 第 5/6 步：终态与测试

AM binding rev4/epoch3 enabled+unfenced+ready，三资源 pending，四项 lifecycle operation 全部 succeeded，dev-org canary 为零。AL 仍保持 detached。专项测试、脚本编译和 diff whitespace 检查通过。

## 第 6/6 步：下一波

下一波新增 AM successor registration：以 AL detach Receipt 和 groupRevision116 为唯一父权威，把九路从 legacy 原子切至 AM，并验证 route revision/group revision、binding/config ref、零 inflight/canary。注册完成后再迁移 definition rev51 disabled 和 recovery rev16 的保存输入到 AM，生成 rev52/恢复 rev17，并由自然 Worker 创建唯一 attempt。
