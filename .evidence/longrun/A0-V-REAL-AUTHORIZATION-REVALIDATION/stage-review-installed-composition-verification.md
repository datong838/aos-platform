# 阶段评审当前已安装运行时组合验证

日期：2026-09-12

基线：`b61f247f`

结论：stage-review 新发布已把同一 concrete installed invoker 的 runtime snapshot 纳入业务 authority 的
prepare/commit exact 封印；replay fast path 保持不读取当前运行时。

## 验证

- invoker 定向 `12 passed`：factory 的调用方法和 snapshot reader 绑定同一对象。
- service 隔离 PostgreSQL `4 passed`：正常发布/replay、未知 IPC 零发布、第五门后 binding revision
  漂移零发布、replay 零新增 proof/runtime read/IPC。
- snapshot reader 只接受 `HostTransaction`；canonical Installation store 不获得裸连接或提交能力。
- 旧 async service 的无 snapshot 内部测试 seam 保留，正式 factory 始终提供 concrete snapshot reader。
- `git diff --check` 与 compile 通过；无公开路由、无安装或租户数据变更。
- 累计关键链 `64 passed`；AR2-7 closure 扫描 1781、分类 147、迁移 93，全部错误数组为空。

## SHA256

- invoker：`6f14f6ad0e00f5a91850baee6de03f608c4678f75c046d84a772866bfdd12242`
- async service：`5ffda95e508ede17a95503d86e31ecbe6fd58685144931272587f924cc3cc3ec`
- invoker tests：`7403b9105bf8ccbb2b0b8e4da6de38c90803cd225ed03d5abd98ff4f4296f463`
- service tests：`54df3880d36cba2a0b92888c1229c9accd245c33b4cce1f5456b71e9eea3ad6f`
- plan：`5e71d1b71d7dbe054134aff1623f0025e1d635856dec988b0fd3d5bbb2303a1b`

## 下一门

审计真实内部调用入口和运行时启动 composition：当前 live directory 尚未由 production runtime control
plane 统一持有，正式 factory 也未挂入 app state。下一波先解决进程所有权与只读可发现性，再决定内部
命令入口；1.5.0 candidate 未构建/安装前不得激活当前 1.4.0 上的新评审路径。
