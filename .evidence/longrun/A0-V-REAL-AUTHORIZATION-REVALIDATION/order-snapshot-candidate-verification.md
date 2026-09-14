# SC4-5e4 订单观察快照与真实源结构核对

2026-09-14；基线5349bbe7；m1不push。父Lease A0-V-SC4-CATEGORY-ORDER-SNAPSHOTS；子Lease A0-V-SC4-ORDER-SNAPSHOT-CANDIDATE。

v3支持严格声明显式删除字段/存活值/删除值，拒绝非法配置与未知删除值；删除覆盖规范状态为DELETED，不从批次缺失推断删除。旧v1/v2语义不变。
订单候选保留全部状态、真实create_time和金额；去掉画像不需要的收件姓名，保留memberId但不声称placedByLite关系已物化。

1.7.0源树5641f4890a2198fd92d6eefc4e68400d90ce7030c8e8e8059a657c09de4ba069保持不变；1.8.0新树d0f2a557e0749a4bc753e18954a2dce368f632d7be8bd3247cece69d04e0c575。相对前版仅bundle.yaml、p05-order.yaml、evidence/bundle-evals.json三文件变化。五类规范对象静态评估通过；未构建镜像、签名、发布安装。

真实源读取使用现有P02保存配置与JdbcConnectorRuntime，只读事务、只输出结构与聚合计数，不记录凭据或客户行数据。证据full-store-source-structure-20260914.json涵盖12类源表；不是正式Fulfillment Receipt。订单185中存活125/删除60；明细235的create_time全部0。旧本地13306不可用不代表SSH源连接失败；复用保存配置后源只读查询成功。

验证：100 passed，7个既有警告，6.23秒；AR2 1909/187/93，五错误数组空；git diff --check通过。映射测试为合成记录；真实探针只证明当前结构与数量，不证明完整采集或业务闭环。

SC4-5e4：订单观察快照1.8.0候选完成，保留关闭订单、真实创建时间和金额，显式删除标志严格验证；100项回归通过。源库只读核实12类结构与数量，订单185/明细235；明细创建时间全0，后续必须通过真实父订单关联解释窗口。静态映射5/12，主库仍先前核实2/12，未发布安装或真实Fulfillment。下一订单明细及剩余6类、真实关联/补齐，再恢复与八场景。
