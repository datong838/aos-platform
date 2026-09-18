# AN direct successor 运行前代码闭包验证

## 结果

本波关闭 saved-input successor 的跨 control family admission 与 Store/元数据长锁问题，未创建 AN、未调用 `run_definition`、未读取商城源、未改真实 Run/Receipt/Binding/路由或资源。

- `PipelineSourceClaimOwner` 只接受同一次整组 recovery Authority 返回的 successor admission；普通 renewal 继续要求同 family 和单调 revision。
- 跨 family 从原 claim ref 解析原 control identity，分别固定原 installation/generation/pipeline/actor 与当前 Authority；只放行方案列出的 successor 身份字段变化。
- `ec_ingress_recovery` 在进入独立 Store 前提交元数据事务，并在每个 derived Store 写入前后重新锁定 Run、比对 parent/saved command。
- Store 前缀已提交后若 current 元数据漂移，保持原 Receipt 并拒绝继续；下一次稳定复核只读回同一 Receipt，未产生第二条。
- API 状态 hash 增加 group completion 和 recoverable Store attempt 文件；a0v089 reason 测试固定只映射登记过的静态 guard 文本，动态异常正文不持久化。

## 新鲜验证

- 纯函数/生命周期首轮：20 passed / 4.14 秒。
- SourceClaim + successor recovery + parent order + 真实 Store runtime PG：34 passed / 2001.44 秒；无跳过、无失败。两种部分 Store 提交恢复均复用原 request hash，12 Run 原子完成，source call 数不增加。
- recoverable attempt/a0v089/API/Ingress/Worker 纯回归：27 passed / 4.49 秒。
- group completion/Worker/controlled saved recovery 串行 PG：13 passed / 210.80 秒。
- 增补 Store 提交后元数据漂移用例后专项：21 passed / 4.13 秒。
- 六个 Python 文件 `py_compile` 通过；`git diff --check` 通过。

一次累计 PG setup 曾与另一 pytest 进程并发修改测试容器的全局 `aos_runtime` role，PostgreSQL 返回 `tuple concurrently updated`，13 项均未进入测试体。停止并发、保持同一代码严格串行重跑后 13 项全部通过；该 setup 竞争不记为产品失败，也不用于掩盖测试红灯。

## 运行基线与限制

提交前只读复查：Runtime Host `ACTIVE/tenantCount=1/canary=0/liveTargets=[]`；Worker `IDLE/hostInThisProcess=false`；18181 health、8434 ontology 与 API proxy 均为 200。当前服务进程仍是上一波重载的代码，必须在 running attempt=0 的空窗再次受控重载，才能声称本波代码已加载。

本波通过不等于 AN 生命周期或经营首链完成。下一步先在空窗重载 API/Worker，核对新增 code hash 与正/负租户边界；随后才以 AM exact detach Receipt 为唯一 predecessor 编写并执行 AN replacement，继续正式 Owner、CAS、Receipt、零 sourceReads 与 unknown 不重发约束。
