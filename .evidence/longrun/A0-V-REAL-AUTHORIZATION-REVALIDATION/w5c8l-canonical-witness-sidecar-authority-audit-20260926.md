# W5c8l｜canonical 见证 sidecar 权限与回填边界审计

## 结论

`a0v_045` 原 claim/member/input 表不可变，不能以原表 UPDATE 作为历史见证回填路线。新增 `a0v_097` **空 sidecar** 是无业务 effect 的结构基础：双租户键与组 UUID、原 claim request hash 外键、原 input 组身份外键、文本大小/JSON object/sha256 检查、RLS FORCE 与不可变触发器。对 runtime/directory/maintainer 不授 INSERT/UPDATE；没有 backfill writer、ACK 或新函数授权。

## 已证与未证

- 隔离 PG head 空表、运行角色 INSERT/UPDATE 无权、旧 reconcile 仍无 EXECUTE、正常 complete 仍有 EXECUTE。一个原保存组夹具由数据库所有者在 test-only 库插入匹配见证后，UPDATE/DELETE/TRUNCATE 均被不可变触发器拒绝，假组身份插入被拒；零二次源调用。
- 结构允许数据库表所有者插入；本波**不是**“任何角色均不可写”。真实 runtime 身份/数据库 owner 隔离仍要作为部署门复核。
- sidecar 的 request hash 以复合 FK 绑定原 claim；manifest hash 目前只核文本自身，输入表没有可供侧表直接 FK 的 `(org,project,group,manifest_hash)` 唯一键。故后继受控 writer 必须在同一事务读取并比较原 input `manifest_hash`/manifest JSONB、原 claim binding JSONB、两份文本解析与存储原值相等；当前 sidecar 行本身不可作为 ACK 权威。
- 现有不可变触发器不阻止首次插入恶意但自洽的文本；历史回填需要逐行只读扫描、拒绝报告、权限隔离与受控插入函数。真实历史全量从未扫描；数值 roundtrip 可能与原 Python hash 不匹配，必须逐行冻结而非修正。
- 真实库未迁 `a0v_096/097`，旧入口在真实库是否仍可执行须以真实读回为准；当前真实 profile 停止，运行/closure 门冻结。隔离表结构 GREEN 不能向真实 Worker 授权。

## 后继 W5c8m 必须做

先方案化只读、限量、零源的历史组扫描和分类（可重建/哈希漂移/缺 claim-input/租户漂移/多组/数值歧义），只输出匿名计数与精确行键，禁止自动 INSERT。隔离 PG 证明所有负例后，另立受控 writer 与真实迁移/发布顺序；不可跨过 Host→Delivery、双 Receipt、原谱系和 fleet gate 直接 ACK。
