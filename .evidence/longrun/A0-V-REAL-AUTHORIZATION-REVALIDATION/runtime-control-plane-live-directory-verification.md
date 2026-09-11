# Runtime control plane 唯一 live directory 验证

日期：2026-09-12

基线：`dce4bbeb`

结论：production runtime control plane 现在持有一个独立、初始为空的
`LivePreparedJobDirectory`；app lifespan 保留该 exact 对象并在 control plane 清除时解除引用。

## 验证

- Red：production builder 返回对象没有 `live_job_directory`，测试明确失败。
- Green：两个 builder 实例各自持有不同 concrete directory；disabled selector 继续零访问，dependency
  wiring 不变；真实 app lifespan 内可取得 exact directory，退出后 control plane 清空。
- production/runtime-startup 串行回归 `28 passed`；directory/invoker 回归 `18 passed`。
- 曾并行运行两组全库迁移测试导致共享 `aos_runtime` 角色 ALTER 竞争；串行复跑全部通过，确认是测试
  setup 竞争而非产品失败。
- AR2-7 closure 扫描 1781、分类 147、迁移 93，全部错误数组为空；`git diff --check` 通过。

## SHA256

- control wiring：`ece42c19d637ca264f0e6bacc265169ef1ae280fd65ce4df09ac3930c7c4b5e2`
- production tests：`cfb83f4beb2f48d93a135239705f7c5a4b7b7534eecf69c86cf81e95bf004d71`
- startup tests：`5db65270ec08e28e6494113ab52e4d4ea66c1a60a08e604db67acd4063c4f6ee`
- plan：`02dae677b1876f8b958d56927545c1e12f7cc6eb0a10bbd8f4e972198cd533a6`

## 下一门

production host 目前只装配 recovery/configure/disable worker，尚未装配会创建并持有 PreparedJob 的
runtime-apply/verify/enable orchestration。下一波审计并实现该串行进程所有者，把 job 登记到本目录；
没有真实 owner 时目录保持空并 fail closed。
