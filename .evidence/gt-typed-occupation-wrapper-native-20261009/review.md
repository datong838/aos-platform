# 同连接占用准备包装复审

唯一产品文件aip_physical_capacity_occupation.py：原未跟踪模块的字节前缀完整保留，追加prepare_target_occupation，在原atomic Task既有范围纳入版本。真实psycopg SCRAM/require_auth/已有事务/dict_row/固定tenant/UUID检查；原消费command重新验证，复用原consume_capacity_source_for_occupation和_consumption_packet，无新认证/协议/哈希实现。

原窄SQL仍是权威；响应经已有PhysicalOccupationPreparation校验，随后与真实conn的tenant/login/xid/pid/role/UTC/serializable/readonly/replication、原plan/Intent/call和Source physical account精确绑定。前后identity不变、packet不变；不commit、rollback、retry、DDL或dispatch。异常仅固定安全错误，抑制凭证输入，事务由caller处理。

真实独立全库RED91.45秒：完整原准备链已建立，缺包装接口AttributeError。独立回滚及原资源保留。GREEN R1包装正向/精确重放/10负向完成，但后段原Judge current approval50秒超时，全节点FAIL66.49秒；独立回滚/六表零/临时探针零/31原资源不变。R2仅移除已封存1610计划四负测及重复ACL/即时提交门，包装10负测和原全manifest回归保持，产品与有效期不变。

R2全原生1PASS100.66秒/noSKIP；正向严格DTO等于原SQL响应、精确重放与同xid/pid，错误scope/假连接/缺命令/字符串plan/缺Intent/未知plan/未知Intent/重复call/错误时区/错误角色均拒绝；原事务仍活跃，最终实际callerCOMMIT23514拒绝。独立xid aborted/六准备表0/Source1/Owner无LOGIN成员/临时探针0/接口清理/31原资源身份启动卷端口不变。相邻349PASS0.77秒，7既有警告。失败日志与冻结helper hash绑定保留。

本轮包装没有运行路由/默认迁移/实际admission/unknown状态/费用Usage/Judge输入结果/transport/finalizer或最终COMMIT许可。原五父Task继续ACTIVE。Browser不适用未接运行入口工件；原批准期限与真库未动。下一safe候选：严格包装跨事务/命令变异的独立原生负门，或单腿真实risk/Judge依赖设计；不补造外部结果。
