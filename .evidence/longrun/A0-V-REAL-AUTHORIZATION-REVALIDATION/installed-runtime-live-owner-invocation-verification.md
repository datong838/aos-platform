# 已安装运行时 live owner 一次调用验证

日期：2026-09-12

基线：`6f5acc3d`

结论：现有签名 preparation owner 可在不暴露 session、不创建第二容器的条件下执行 package 唯一绑定的
一次调用；这只是 live owner 能力，尚未构成当前 Installation/generation/epoch 的调用授权。

## 验证结果

- Red：新增四项合同测试最初因 `PreparationOwner.invoke_once` 与
  `PreparedJob.invoke_selected_once` 不存在而全部失败。
- Green：live owner 原位调用、同 owner 串行、错误零重试、package id/hash 唯一选择和 stop 取消收敛通过。
- 首轮相关回归：`26 passed, 5 skipped`；累计 owner/worker/consumer/coordinator 回归：
  `33 passed, 35 skipped`。跳过项均为需要显式 OCI/隔离 PostgreSQL 开关的既有专项。
- AR2-7 closure：扫描 1779、分类 144、迁移 93；hash、未分类正反向依赖、bundle 跨层 import
  与动态引用错误数组均为空。
- `RuntimeSession` 仍负责 declared operation 校验，因此旧 1.4.0 对未声明的第五门保持 fail closed。
- `git diff --check` 通过；未修改 Installation、binding、Registry、package 版本或租户业务数据。

## SHA256

- `preparation_owner.py`：`bade722713d0fee9e4777283e4493c5f5b6019103b2e147cdcd292367cc41374`
- `preparation_worker.py`：`48ebb2ebccc8c2705ef378273dbc22dcba13e08069e85dbbfa46df6ff8cd715b`
- tests：`bd75d693432349599d8e32ea5dea07821382bc8a8d7cdd799462c6e719db96a2`
- plan：`326eb2390d54da33914fec26432a2b7779d6f3fd51aabdde832580296e2cbf31`

## 风险与下一门

`PreparedJob` 仍只由 preparation consumer 持有，生产 runtime directory 尚未提供 exact live-job 查找；
当前性复核也尚未包围 IPC。下一波应增加进程内 job directory 与 Installation/generation/binding epoch
前后快照校验，再装配 stage-review service。没有该门时不得声明 installed invocation 已可用。
