# W5CB4 BG-00al｜Eval writer unknown 提交只读对账方案

## 上位边界

231-5 规定命令结果未知时先读取目标 Receipt/authority，不猜测状态或重做副作用。BG-00ak 同事务提交后若连接断开，调用者不知道是否成功；重复调用会触发唯一键，不能当作幂等成功。BG-00af 已有当前持久 Report/全 case/双签名 reader。本波复用其纯读取，不增加写入、重发、Host/Gate。

## 文件级计划

1. 新增 `services/aos-api/aos_api/aip_eval_writer_reconcile.py`：调用方提供已开启的精确租户 `aos_runtime`、repeatable-read/serializable、明确 read-only 事务。函数在事务中取数据库当前 cutoff，调用 BG-00af 全 case reader。仅当当前签名/撤销/Owner、Report、双 Receipt/sidecar 全精确匹配返回 COMPLETE + proof；所有缺失、部分、漂移、跨租户或错误快照都返回 UNKNOWN，无 ABSENT 可重发状态，绝不写表。
2. 新增 `services/aos-api/tests/aip/test_aip_eval_writer_reconcile.py`：先 RED。使用 BG-00ak test-only 独立 writer 真提交后的持久证据，在独立只读 runtime 事务中正向 COMPLETE；未提交、仅 Report、跨租户/错误 role/非只读或签名错返回 UNKNOWN。test-only fixture 负责精确清理；当前库只读。
3. 专项/相邻累计、方案一致性复审、verification/精确 m1 commit，authority/01/06、313 和 D-wave 登记。正式来源/Owner/ACL/G2/S3/Gate/首链仍禁入。
