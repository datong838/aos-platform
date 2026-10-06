# SQL原文字节计算阶段验收

基线512b4de7/AOS-001374，原publication Task同Owner/Lease施工，当前Task与完整Goal仍ACTIVE；新增范围仅原登记publication_store.py和原publication测试/契约及本证据目录。未创建151/152迁移、未改权威库/现有恢复副本/正常服务，未授Source/Host/Provider执行权限。

## 证据

- sql-profile-red.log：新store不存在导致12项setup errors，是编码依赖RED；随后最小函数原生12项通过/14.70秒。
- 原始json递归遍历保留重复字段，C排序、整数词法、UTF8字符串to_json、数组顺序，重生成紧凑UTF8与原始raw逐字节matching；2MiB/depth32/array1000/object1000。bytea入口返回通用jsonb视图，不代表typed业务文档。
- PRIVATE计算SQL两函数均INVOKER/STRICT/IMMUTABLE/search_path=pg_catalog，PUBLIC schema/function全撤；未来递归helper只有private owner直接执行，原issuer不获helper grant。UTF8真实DB编码门，NULL返回NULL，正式接受入口必须拒绝NULL。
- 改有序string_agg，避免逐项array_append复制大文档；近2MiB/1000项实测及EXTENDED/EXTERNAL精确2097152接受、2097153拒绝。空容器/null/bool/零/负整数/Bigint/中文/Unicode C排序/转义、数组/对象1000边界、container深32接受/33拒绝，完整permit/bootstrap/PublishedSource原文可计算。普通role默认schema与function拒绝，仅隔离测试明确双grant才可调用，全部同事务rollback。
- 首累计sql-profile-adjacent-r1.log终结164 errors/52.39秒，旧conftest迁移a144时checkpointer被signal9终止，5433进入recovery并自行ready；fixture-recovery-readonly.json保留原事件。历史OOMKilled不能单独归当前故障，2GiB VM内存压力是支持性证据，当前根因并未被后续通过证明。
- 仅停止本线程已Delivery的两个旧验签r1/r2 no-network独立实例，精确containerId/image/label先核，卷/镜像保留，最终r4和权威服务不动。closed-verifier-resource-release.json保留。重试显式RETAIN_DATABASE=1/USE_SHARED_DATABASE=0，累计164passed/16.04秒。
- 最终新增UTF8/精确大小与Python OBJECT拒绝stage后，sql-profile-adjacent-final.log：167passed/7既有warnings/17.36秒/exit0。final源码hash与只读rollback核对见sql-profile-rollback-and-hashes.json：private schema0、test role0、原crypto函数1，未持久安装计算函数。
- 独立route_supervisor最终只读复审：本范围无新重大阻断，可作为已验证依赖继续；指出历史方案状态句需修订，已最小标明历史与当前encoding通过。无UI变更，浏览器不适用。

## 后继完整退出

本模块没有可运行publication Store。通用编码接受任意规范JSON（含scalar）不意味着typed文档通过；完整SQL函数必须独立严格字段shape/类型/refs/期限/原批准检查。受控anchor/root/permit取钥、原publisher身份、撤回epoch协调、supplier+fingerprint稳定全域映射、同caller待签bytes与最终签发验证、原子publication COMMIT/rollback/replay/unknown对账、consumer全部仍pending。本Task禁止helper-only Delivery；下一步冻结完整函数/body/锁图并另登记152精确迁移scope，不覆盖已存在151。正式自然首链、八工作台观察及发布仍未完成。
