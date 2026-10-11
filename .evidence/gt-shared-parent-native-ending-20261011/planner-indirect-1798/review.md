# 实际规划函数间接依赖

对原64观察OID逐一核签名与prosrc hash一致。在同隔离库REPEATABLE READ READ ONLY递归prosupport及pg_aggregate八个函数槽和sort operator实现，得到78函数、增加14个、17条声明边。包含generate_series/unnest/count支持函数、sum状态累加/合并/序列化/逆累加，以及jsonb_agg transition/final。无函数调用或库写。

这是目录声明依赖，不是17条边实际执行或全路径闭合；聚合/native内部还可能间接调用类型输出/比较等，缓存与未执行分支、规划改写、包信任和生命周期仍未覆盖。不可因全部内置或标immutable/stable推断可信无副作用。后续应将这些依赖接到完整包与固定validator的原生验证合同，继续完整事件固定点/耐久COMMIT/unknown；不新增业务许可或组件Delivery。
