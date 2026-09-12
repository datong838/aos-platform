# 首链绑定只读预检与连接隔离修复

模型解析器原先 exact Gate 与 health 查询绕开已注入的 Store；真实预检产生 release gate read failed。现统一继承 ModelRuntimeStore 的连接及评审权威，35 项 resolver/治理回归通过；默认使用场景不变。

D01/D02/D03 从当前本库提取 Skill r2、capability 最新 published、各自 exact frozen EvalContract、内部用途 Bundle、Route/Policy/Provider/Budget。12 项新边界用例通过。主库和独立克隆预检均无写入，三项均仅剩 MODEL_ROUTE_BLOCKED / PROVIDER_HEALTH_UNAVAILABLE；未激活数字同事，也未新建经营任务。

一次独立健康调用超时，返回 provider_timeout，healthObservationWritten=false。允许重试的是无业务副作用的健康探针，每次独立日志，不覆盖未知/失败记录。未取得成功前不写绑定可用标记。

新领域包 Host 于 02:32:44Z 完成 307 秒观测、4 次续租、三容器存活、同 generation，跨过初始五分钟。尚未跨旧 36 分钟失败点；继续独立观察。
