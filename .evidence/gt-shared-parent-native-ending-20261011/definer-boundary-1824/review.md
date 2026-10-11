# 固定验证器提权目录核查1824

1807终态隔离库239持久观察函数中四个SECURITY DEFINER，当前OID/签名/正文SHA/Owner/proconfig逐项精确一致。固定search_path=pg_catalog。runtime无四函数EXECUTE；physicalOwner可执行四个，modelIssuerOwner仅Receipt-origin。PUBLIC无grant。两Owner无登录/超级用户/角色创建/数据库创建/复制/bypassRLS及成员关系。runtime/两Owner均无这些函数所在public schema CREATE权限。

实际完整collector正文仍要求原session/runtime/SER-RW/UTC/origin/租户/pid-xid及原Receipt、八节点hash和原risk/Source/physical等价，并返回nativeEndRequired=true/durableDeadlineEstablished=false/executionAllowed=false。元数据观察不授予原生完成能力。

未发现EXECUTE/LOAD/set_config字面线索仅作检索事实，不作为解析/全部分支/原生内部无副作用证明。四函数正文已冻结供后续精准调用审查；不把观察239清单当完整允许集合。下一回到未覆盖调用/操作符/cast/回调与完整Main native arm/finalclock/COMMIT，避免继续用超级用户独立攻击面替代业务可达证明。

只读目录事务回滚，未调用业务函数、未重放Source、未改权限或正式数据。原Task仍ACTIVE，完整Delivery未成立。
