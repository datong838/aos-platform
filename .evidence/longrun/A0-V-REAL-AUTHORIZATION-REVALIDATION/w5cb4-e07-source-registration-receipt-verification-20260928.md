# W5CB4 E07：数据源登记持久 Receipt 与当前卷升级验收（2026-09-28）

## 本波结果

承接方案 `5a4935a1`。原 `/v1/sources` Owner 保留，新增 `a0v_108` 的 tenant-scoped 不可变登记 Receipt；带 `Idempotency-Key` 的新产品提交与源配置在一个事务内落库，同 key 同请求只回原公开结果，不同请求 409。按原 key 的 GET 只读回执，不加载连接密钥；老客户端无 key 的既有行为兼容。前端 pending 仅存 ID、运行时、配置修订、随机 key，不存密码；同次响应及权威源/Receipt 一致才解冻，丢响应后只查原 key，Receipt 缺失仍冻结；保存后仍不自动 `/test`。正式 SourceSelection、自然 worker 和旧 12 Run 未被启动。

## 测试和当前时点备份

- 后端新专项、既有源登记、探测边界与精确路由 manifest：32 passed、2 subtests；前端 DataPage 与邻接：22 passed；TypeScript noEmit、Vite production build、`git diff --check` 均通过。路由总数 4519、摘要 `d5ea6a6666a92e29e952276238a4f9b04f522360c4e3db0b86cd9c13e1e68e4d`，OpenAPI paths 2714，无新增重复路由。
- 升级原卷前从当时 `a0v_107` 库生成完整 custom-format 归档：`/Users/ddt/work/projects/ai_agent/.aos-e07-current-backup-8bzUvM/aos_current_preview_20260927_a0v107.dump`，权限 0600，SHA-256 `205e9904b6c6f7f907ab0a857ba9f00b2444575f4eeaffccb820ea4945daa255`。`pg_restore --list` 可读；完整恢复为独立 `aos_e07_receipt_isolated_20260928` 并成功升级至 `a0v_108`，不靠历史卷。
- 独立克隆库中以合成 file 源验证：同 key 重放配置修订相同且没有二次源写；不同 payload 同 key 得 `SOURCE_REGISTRATION_KEY_CONFLICT`；`dev-org/dev-project` Receipt 为 0，Receipt 公开元数据无密码。合成源仅在克隆库，未登记到当前业务库。

## 当前库升级与全栈验收

升级前只读基线：schema107、安装1、发布版本4、正式 MethodRevision1、源0、RuntimeBinding0。停止原 8080/8434 后，原 `aos-a0v-recovery-pg-data` 卷中的当前 DB 仅运行 `a0v_107→a0v_108` 非破坏性迁移；回读 schema108、安装1、版本4、方法1、源0、绑定0、Receipt0，方法内容 hash 仍为 `784dacfa959cfaabc3e2fdf1bb95f367514624e163680e0306896d8914e120c2`。原容器重启而非重建；预检 GREEN、migration disabled、Runtime Host0/worker0，8080/8434 HTTP200、18181 无监听。只读 HTTP：`org-org/dev-project` 不存在 key 返回404，`dev-org/dev-project` 返回403。浏览器重新加载 `/data` 并打开/退出向导，当前数据源总数0、近24小时同步0；没有真实凭证、POST、源读或同步。

## 方案/代码一致性和风险

仅 `source_registration_receipt` 新增，保留配置修订触发器及既有源 Owner；没有新建第二套来源权威、没有删除旧卷或旧业务行。Receipt 由当前 `aos_runtime` 原事务写入，响应字段由固定公开白名单投影；数据库列尚未再用约束独立检查公开字段白名单，记为后续硬化项。旧 E06 已留下且缺 key 的待对账标记不能自动解冻，必须保持冻结，不能人工清标记后重发。跨标签页极短竞态还需服务端同源不同 key 序列化保障与真实并发集成反证；现有源 advisory lock 已覆盖同源写序列化，仍需正式并发测试。本波不证明源可连接、商品数据新鲜、SourceSelection 获准、自然链闭合或八场景完成。

下一波 E08：复习 231/231-9 与当前已装包/管道配置，选择“正式源配置→获准 SourceSelection/自然更新”最小生产者；缺真实源授权时继续做可独立完成的下游配置代码，不读取商城源库或回历史堆找行。每日仍以最新代码和当前命名卷完整重启验证，之后继续 Loop。
