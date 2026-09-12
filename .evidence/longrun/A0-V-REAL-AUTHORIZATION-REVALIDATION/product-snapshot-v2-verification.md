# 商品快照v2转换合同验证

2026-09-13 02:53，m1，基线0e22e375。新增pipeline_snapshot_materialization_v2.py及专用测试，v1入口只按显式schema版本委派；未改签名包、候选目录、当前安装、运行API或商城数据。

v2支持严格decimal/text、源modify_time→create_time fallback、显式删除与状态。price保留十进制字符串；float、非有限及超出边界值拒绝。源时间晚于观测/缺失时拒绝，不能用轮询时间充当商品更新。删除只能由专用tombstone事实产生，不允许普通状态映射自称DELETED；状态目标属性明确声明且不能覆盖已映射字段或常量。非空links、旧soft_delete与incremental_cursor声明拒绝，避免静默漏执行。P03链接尚未支持。

测试首轮17 failed/7 passed；实现后canonical Product属性缺失1 failed/55 passed，已在方案中补齐显式shopId/title/categoryId/status映射；评审新增“普通状态不能伪造删除”先红1 failed/27 passed再修正。最终新v2、旧v1、选列/选源、既有PG受控读取及完整执行回归共110 passed，7.68秒，7既有warning。v2本身纯转换与SQLite真实Owner测试，PG部分仍是既有P01受控路径回归，不能冒充v2真实源/PG新业务验收。SQLite连续两次不同观测时间读取同一源商品仅产生1个authoritative outbox事件，进入原canonical对象后金额和tombstone正确。

AR2 ar2-7：1809 scanned/158 classified/93 migrated，五类错误数组空，diff检查通过。02:52当前Host仍ready/enabled/unfenced@4，263续租、16256.8秒、3容器running、canary安装0；这不是连续经营效果观察。

真实目录/首链盘点after-p01-business-entry-inventory.json：当前core1.3、Niushop1.4、growth1.7均无frontend声明；dispatch binding、business schedule、Occurrence均0；仅P01正式图。当前Sidebar空目录是已知未接入状态，不通过移除legacy过滤补八个静态菜单。

下一波优先对照P02实际mapping和canonical Product属性形成新候选：金额非负等validation不能丢弃；完整site状态范围避免上架过滤漏掉下架/删除；通过候选资格、Schema实证后才安装新版本和正式P02图。并行含义仅清单保留，执行继续m1串行；自然事件配置/消费者/dispatch与前端产物接入仍待后续完成。不可修改已签名1.4或声称商品首链完成。
