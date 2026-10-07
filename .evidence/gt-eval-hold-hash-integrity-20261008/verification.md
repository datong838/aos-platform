# Eval 已有预留完整事实校验交付

Rules：231八步；先plan/精确Task及Lease；原生RED后最小修复；正式库只读、不部署、不push、m1唯一写者。Task gt-eval-hold-hash-integrity-20261008，仅本范围完成，父联合准入与长期Goal未完成。

问题与修复：原Eval hold已有预留分支只核五字段，实际runtime在合法隔离申请/原checker审批后的首次INSERT可写入错误content_hash，原hold返回而未拒绝。原生RED DID NOT RAISE，外层ROLLBACK且独立读取该申请预留0行，Provider0。证据在父Task eval-hold-hash-native-red.log/json/rollback.json，原HEAD40c220。

修复已在返回前核完整存储行canonical hash，再核与当前原申请、proposal/checker、BudgetPolicy/BudgetRevision/Price/currency/upperBound构成的原immutable payload hash相同。新预留继续用原payload和canonical算法；原先五字段比较、原前置授权及费用门、共享桶顺序、SQL结构、append-only/RLS/旧迁移未改。没有授予执行或修补现有数据。损坏旧记录将拒绝而不会自动清账。

验证：专项15 passed；专项+相邻四文件最终50 passed/无skip，7既有警告。新随机全迁移库 aos_test_3bc353e1ed36_ti4_test 上原申请/独立审批/原native hold：准确hold及same-ID replay通过，错误hash首次INSERT后hold拒绝；测试预算窗口全ROLLBACK。独立SERIAL READ ONLY回读cluster7693564235776004128，Model预算hold/link/AgentRun/Modelcapacity四表0行，预算held+submitted+unknown exposure=0；前缀来源/审批审计与库保留。前缀不代表真实Provider/Model质量或自然业务运行。所有claim与源码文件hash另存source-bindings.json。

复审：current immutable字典从原插入位置前移到existing查询后，字段不变；新增验证独立检查stored与expected，防止错误来源即使重新hash一致也被复用。canonical函数未复制；字段映射用于准确持久列还原，缺失/不可序列化值统一域拒绝。UUID字符串规范保持。无UI更改，浏览器不适用。未取得独立模型督导PASS，不伪称独立审阅；本次为代码自审及原生测试。

运行包装器沿前轮克隆的header/scope仍有budget bridge模板描述；nodeid与本记录明确实际为hash integrity反例，原始历史claim不改写。构建复制脚本曾在Python解析阶段SyntaxError，无DB或文件效果；修正后独立新claim执行。未重放未知操作。

剩余：完整Source/Pool/Intent联合准入、合法普通/Eval费用锁竞争与Model/Route typed执行证明仍pending；当前API未加载此提交，不以本修复宣称首链通过。
