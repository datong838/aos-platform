# 完整主链路由独立复核

Rules：231与已批准联合方案；只读现有Prime身份、工具全部禁用、冻结HEAD/hash/AOS-001667与本Task；原旧attempt未知不重发，不启动后台daemon、不改全局设置、不自动执行建议。仅本Task证据目录，无产品修改/DB写入/Provider/重启/Goal状态操作。

候选A：完整父cap下risk与实际inflight分离，依赖全case原批准、真实终结/Usage与完整joint、token来源，隔离设计实现已授权。候选B：Source严格实际结束协议，依赖明确提交语义与数据库内核/外部协议；产品裁决已异步请求，未答复仍严格拒绝。候选C：原Target已知持久proof→Judge实际输入与可信root/transport/joint来源，隔离范围已授权，必要签名存储不能当真实Provider来源。请复核路由而非只判断局部testgreen。

使用scripts/long-task-watchdog/aos_review.py --request本Task request.json --output新result.json。64KiB内完整冻结材料、实际原证据hash和摘要；单次新request，不复用旧unknown request。错误结束即失败，即使exit0；未知仍先读transport/attempt，不重发、不消费。成功后只读消费绑定同HEAD/hash，PASS不授调用。明确次序/依赖与未完成全Goal，不另造helper-only成功标准。
