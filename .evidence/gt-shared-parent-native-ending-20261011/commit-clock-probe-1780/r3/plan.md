# 原生提交检查与持久化时间边界反例

Rules231、原完整 NativeEnding Task/Lease、m1 单写。候选一：PRE_COMMIT 到实际持久提交的时钟窗口实测（本轮选择）；候选二：独立受控完整安装/profile/bootstrap（依赖独立专用 Root 与生命周期，未获正式安装权限）。不得以任何组件结果缩小原 Main 八节点、四证书、Source、完整风险/物理、Receipt、fixedpoint、最终时钟、COMMIT 与 unknown 分母。

新增文件仅本目录 plan.md/probe.c/Dockerfile/run.py、构建/安装/三次固定试验 intent/terminal/readback/review。不改产品目录、签名验证器、现有 guard 或 Root。复用已确认隔离 PG16.14 容器/cluster，新增唯一 test_owned_clock_ schema 和全新仅 superuser 测试函数，PUBLIC/runtime/issuer关闭。不操作正式库、不重启、不回放旧试验。

在现有缓存 SDK 新层、networknone、Werror 编译测试库，scratch 无挂载容器仅提取不启动。固定三案例各一个新 backend：已过期 PRE_COMMIT 拒绝；足够期限无延迟提交；200ms 期限检查通过后另一 PRE_COMMIT callback 固定睡眠600ms，记录睡眠结束时钟，再实际 COMMIT。回调只用时钟、固定睡眠、NOTICE，不作 SQL/权威读取/写入。普通调用事务只写唯一标记。安装 intent 和每次 COMMIT intent 先落盘，未知结果仅按 XID/schema 标记对账，绝不重发。

独立事务读取 XID、标记及 DB 时钟；检查 NOTICE 中检查时刻 < deadline < 睡眠结束时刻 < COMMIT callback 时刻，且 XID committed。结合冻结 upstream xact.c 顺序说明 PRE_COMMIT clock 不证明 durable deadline；不把 COMMIT 后报错当回滚，不把客户端耗时当持久提交时间，不宣称直接测到磁盘 flush 时刻。同轮保留既有签名/五闭角色、原 pending reader 和容器启动身份。无生产授权或完整 Delivery；后续精确语义裁决不得暗中放宽原截止要求。
