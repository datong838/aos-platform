# License正式写者合同冻结边界（尚未实现）

## 当前源码事实

`aip_production_contract_store.py` create_evidence_bundle委托build，build冻结修订并写build/create两Receipt；revoke先_replay，再exact hash，已存在事件则不重复插入，最后Receipt及commit。生产代码没有epoch、共同锁和正式restricted writer。`w2_005`给aos_runtime撤销表SELECT/INSERT，故只在Python连接工厂包epoch不能防直接SQL绕过。readiness license_evidence_available逐ref另连读取，属于preview，不能代替受限事务命令锁/重算。以上来自本次源读取，不依据旧文档推断生产实现。

## 不变量

1. exact租户/bundle/revision/content_hash是来源键；License内容仍来自已授权冻结修订，epoch不授予License可信性。
2. 正式初始化必须和正式source冻结/issuance Receipt同事务；旧行不能无来源自动升权，缺head须fail-closed，backfill只能独立迁移门。初始化、撤销、恢复、升级均不得从客户端epoch获取权威。
3. evaluator锁顺序Installation→Registry→按稳定exact键排序的source heads→业务Binding/Receipt；writer不能反向取得Installation/Registry。旧快照看到已变head必须40001或拒绝，无Receipt；读到新快照已撤销42501/无Receipt。
4. writer在_replay之前取得exact来源互斥；同key同body重放不改变head/event/Receipt；不同body按原hash合同冲突；并发同key以来源锁序列化，错hash/失败事务无残留。不同key撤销同已撤销来源是否增加epoch须明确语义：优先只在真正新增撤销事件时增加，现test-wrapper每新key推进不能直接生产化。
5. 所有实际撤销写路必须数据库强制推进head，直接SQL同样受约束；普通runtime不能任意写epoch或绕过source匹配。可检验候选是撤销事件INSERT触发器在同事务推进exact head（唯一事件保证一次），再用受限写入口做replay前锁；不是把runtime UPDATE(epoch)测试grant照搬正式。
6. FORCE RLS、固定search_path、definer无BYPASSRLS/无登录、PUBLIC execute revoke；锁入口身份与signed安装/Owner/current authorization不能只看GUC租户或普通runtime权限。现测试角色不等正式身份。
7. 真实迁移必须保留当前命名库/卷，独立备份恢复和零执行窗口；不得在本次测试工作中执行迁移。正式DB强制门演练先在一次性库，不创建第二authority。

## 下一波 b74 文件级候选

仅原两个extension_runtime测试文件及b74 evidence；先让真实Store在不包epoch UPDATE的连接上撤销，证明event成功但epoch不变的RED。然后一次性库限定本波新exact来源的临时event触发器候选，验证event/head同事务、raw INSERT与正常Store均不能绕过、missing exact head/cross tenant失败关闭；不改w2_005或生产Store。原b73请求级锁仍用于重放串行，不冒称正式入口授权。完成后登记service pre-replay lock与trigger最小生产改动清单，须上位完整正式设计/迁移门，不能靠测试PASS直接装入真库。

八依赖统一与W-L20来源绑定仍独立待验；本合同不宣布这两个目标完成。
