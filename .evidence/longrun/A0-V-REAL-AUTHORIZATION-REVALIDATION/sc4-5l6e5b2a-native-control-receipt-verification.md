## SC4-5l6e5b2a 原生Task控制回执消费修复（2026-09-15）

基线455bfa94，m1/AOS-000573。原TaskStore._control_request保存裸SHA256，分析消费端原先自造带sha256前缀的hash，因此真实原回执被拒绝。先补snapshot-resume-design.md，再仅修改ecommerce_growth_runtime_adapters.py的_strict_resume_control_receipt与_verify_resume_commit expected_control，均复用原TaskStore构建器。原严格字段、非bool正整数版本与字符串约束保留；不接受伪造前缀，不改变任何旧保存格式或原表。

Red为原生控制请求8项失败6.50s（/tmp/sc4-e5b2a-red.log）；修复后分析Host/可恢复运行合同56 passed /5.70s（/tmp/sc4-e5b2a-pure.log）。18432隔离PG新旧恢复路径8 passed /16.60s（/tmp/sc4-e5b2a-pg.log），其中读取实际保存控制payload并调用strict消费端。额外原旧统一恢复校验测试先暴露测试使用不存在的requirement.exact_ref，改为原命令的严格Requirement ref后1 passed /6.53s、4 deselected（/tmp/sc4-e5b2a-legacy-pg-final.log）；它经过原Task/Run实际恢复、当前timeline与domain Receipt，再由原_verify_resume_commit验证原生控制hash。旧数据就绪仍是named fixture，未宣称真实水合/十二源完成。

测试环境补充：原tests/conftest.py的autouse为所有测试（包括纯合同断言）创建、升级并删除一次性aos_test_*数据库，纯指断言层级，不等于零数据库初始化。未显式指定基础连接的纯测试使用原默认本机测试服务，未升级共享aos_meta；业务PG回归明确18432隔离。后续测试统一显式18432基础连接。主运行库仍最后只读核得a0v_038；本波无主升级/安装/商城读取/模型调用，不push，230 L0挂起，用户原改动保留。

AR2 1951扫描/192分类/93迁移，错误列表空（/tmp/sc4-e5b2a-closure.log），编译/diff与memory validate通过。下一波e5b2b接快照统一Host与AnalysisRuntimeReceipt，普通注册表仍不得直接授权快照；e5c已提交只读回查/未知结果，e6真实起点与完整十二源、Outbox自然消费、主升级安装、真实首链/八场景/观察和发布判断继续。
