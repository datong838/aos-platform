# Runtime lifespan live scheduler 启停验证

日期：2026-09-12

## 结论

新增一条使用 concrete `RuntimeHost`、`RuntimeTenantAssignment` 与 `LiveInstallationScheduler` 的 lifespan
组合合同。线程事件证明 ACTIVE 后台任务实际完成至少一次空 pending descriptor 读取；factory 调用为 0，
scheduler owners 始终为空。lifespan 退出后 host 与 scheduler 均 closing，后台任务、stop events、control
plane/selection state 按既有路径清除。

## 实测

- 新增及既有 runtime startup composition：14 passed。
- startup、production selector、host、directory、scheduler、pending 邻接回归：92 passed。
- 三平面数据库身份与无 pending lifecycle 真实 PostgreSQL：11 passed。
- `py_compile`、`git diff --check` 通过。
- AR2-7 closure validator 通过：1786 个 Python 模块、156 个分类模块、93 个迁移模块，全部错误数组为空。

7 条既有框架 warning 与 pytest 退出时既有 JDBC 日志流关闭提示不改变 exit code 0。

## 一致性与风险

- 本波没有修改生产代码；验证补齐了 9.39 之后真实 host/scheduler 在 app lifespan 的启停证据。
- 空 pending directory 保证没有 owner 构造、OCI create、claim/ACK 或租户业务写入。
- 这不是 signed 1.5.0 package 的真实安装证明；当前 1.4.0 仍不可变且缺少第五门 operation。

## 下一波

审计当前 ecommerce package 的 1.4.0 manifest、签名制品、operation declarations、Registry/Installation 真值与
1.5.0 版本规则，形成 exact candidate 文件清单和发布/安装前置条件；先生成可评审方案，不原地改 1.4.0。
