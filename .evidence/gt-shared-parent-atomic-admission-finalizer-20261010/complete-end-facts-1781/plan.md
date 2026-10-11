# 固定完整八节点结束事实收集入口
Rules231、原joint§3/11.3、Main implementation-plan-1698、AOS工程交付规则、m1单写/正式库只读。上一波 native PRE_COMMIT clock 反例已收口。候选：一，复用原完整Receipt绑定核建立结束事实入口（本轮）；二，专用包bootstrap/currentRoot/完整native生命周期，依赖正式独立安装来源，隔离研究可继续但不授Root。

具体产品文件：services/aos-api/aos_api/aip_shared_parent_atomic_admission.py；services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py。证据仅本目录；原 Main Task/Lease 同Owner受支持续租，不改变原分母。先冻结全部原SQL生成器byte hashes，RED新入口缺失，再最小新增。

从原 v2 Receipt binder 精确提取原六物理节点+pendingOrigin/endAuthority的完整校验段，不复制简化Source/manifest/cert/两父risk算法，不修改原生成器。新入口只接plan/receiptHash/当前xid/pid，固定Owner/search_path/无PUBLIC或runtime/issuer执行权限。锁读取真实v2Receipt及其原六节点，复用原Source retained reader与FINAL_CALL（四证书与两独立原批准仍由原核验证），最后原FINAL_PHYSICAL比较包含全部历史未决物理risk的精确封闭set。要求八hash字典完整等于sealed Receipt，reject extra/missing/drift，不接受caller SQL/节点列表/facts/allowlist，不使用更新physical account的旧producer。

返回仅来源精确结束facts与观察时钟，executionAllowed=false、nativeEndRequired=true、durableDeadlineEstablished=false；它不arm、不COMMIT、不证明所有RI/event已drain，也不授Root/Source或业务权限。最终deadline聚合/固定validator生命周期/完整包来源/actual positiveCOMMIT/postcommit unknown确认继续同完整Task，不以本构件交付Task。

验证：RED缺入口；真实PG事务内安装完整依赖并编译元数据/ACL/恶意caller拒绝且rollback函数absent；封闭编译器对原Receipt绑定边界/新写者/物理producer漂移fail-closed；旧全部生成SQLbyte exact；专项及相邻累计。仅现有明确隔离PG库，保留原guards/签名/闭role。若完整合法Source同caller正向未执行，如实保留未验，不能以元数据或字符串测试称八节点业务完成。无前端变化，浏览器不适用。
