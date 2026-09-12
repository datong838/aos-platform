# 商品经营候选状态规则验收

2026-09-13 05:13。方案 product-candidate-status-plan.md；数据基线4928937e。

- RED：新模块未实现，定向测试收集报ModuleNotFoundError。
- GREEN：候选状态测试与实际Owner源事件契约测试共56 passed（4.75s），7项既有警告。
- 提交后审查发现新测试文件名称与已有候选包生成测试重名；立即从4928937e精确恢复原文件，将新增测试独立为test_niushop_product_candidate_status.py。三文件共同验证59 passed（4.17s），原有3项保护完整保留。未amend历史提交。
- 真数据只读核验：从IngressJournal原保存命令读取65条；39 ELIGIBLE_STATUS、18 INACTIVE、8 DELETED；sourceCalls=0、businessWrites=0。详见product-candidate-real-observation-v1.json。
- AR2清册验证：1811模块、158分类、93迁移；hashErrors、双向依赖、跨层导入、动态引用错误列表全空。
- 自审：代码位于Niushop平台适配包，不将平台字段放入core；无外部I/O、不改变原输入、不写旧状态和Receipt。scope/platform/shop严格相等，枚举与布尔/整数不隐式转换；矛盾或缺失状态不合格。与方案一致。

限制：这只是状态资格，未证明库存、利润、新鲜度和执行权限；尚未包含在新的签名安装版本，也未接入生产消费者。旧1.5签名树保持不变。下架/删除事件仍须消费以撤销旧候选，不能以本判断过滤源事件；标准状态版本化修复、正式登记/消费者、SKU关系与八工作台仍在后续清单。

下一波：复核九项正式业务路由登记的现有权限/所有者入口及initial_store_analysis需要的SourceSelection；先形成具体登记设计，保留固定操作集合、当前安装配置CAS、租户隔离和不可变Receipt，不能直接补表或借用超级用户执行登记。
