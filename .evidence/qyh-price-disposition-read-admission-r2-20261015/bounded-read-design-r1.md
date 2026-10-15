# 价格处置贡献读取：文件级实施方案

## 目标与基线

m1 e58240059，Authority AOS-002034，唯一owner codex-01a13484-f019-7d82-94ce-812396db9124。承接全部231Goal，本波只接通已安装目录下GET `/views/price-governance/dispositions`的可信只读贡献，不授运营准入。旧Catalog成功路径和所有POST不变。原数据READONLY，Host/worker/Provider OFF，原unknown12不重放、disabled Schedule不启用、不读商城源。

原producer探针已实际证明四种kind的typed binding不同于JSON binding、prepared与frozen完整payload hash、冻结继承、观察hash及派生ID、全部修订计数8而非4，且latest observation可以指向非全局latest disposition。仅隔离内存证明，不是生产gate授权。

## 文件与归属

现有主Task拥有router、read_http测试、本evidence及D-wave。先通过memoryctl另登记同owner非重叠implementation Task，四个具体文件：

1. `services/aos-api/aos_api/ecommerce_price_disposition_readonly.py`：新专用reader、固定表/单snapshot/SQL载荷门、strict integrity和稳定失败。
2. `services/aos-api/tests/aip/test_ecommerce_price_disposition_readonly.py`：新原producer fixture/坏行/完整计数/事务及限额测试。
3. `services/aos-api/aos_api/ecommerce_workshop_price_disposition.py`：只把现有kind→operational blockers、receipt type和allowed outcomes字典抽为本模块纯函数，原prepare/record调用它们，reader复用；不改resolver、签名、写入、幂等、原DTO或legacy贡献行为。
4. `services/aos-api/tests/aip/test_w6_06_price_disposition.py`：添加共享纯规则与原producer行为一致性验证，保留原测试。

不改Web、DDL、AIP/预算、Research writer、依赖锁或用户dirty。任何额外文件先登记。

## 一致截止面及完整有界计数

使用原connect_read_only，一个REPEATABLE READ READ ONLY事务，读取transaction_timestamp；固定四表case/contract/disposition/observation，tenant双列绑定，排序created_at/revision/identity。不增加created_at<=cutoff过滤隐藏未来坏行；选中未来时间整体失败。

第一阶段只返回outer identity/revision/hash/time与octet_length(authority_data::text)，各表LIMIT 513。单表最多512行，四表合计最多512行，单行最多1MiB、合计最多8MiB；任一哨兵/尺寸/类型错误立即失败，不返回部分计数。SQL查询本身不向客户端传输payload。对contract同样有界读全表，可能因无关历史contract超过预算拒绝贡献；这是保守整视图不可用，不能裁掉contract后声称完整。

第二阶段仍同事务，固定同范围/顺序/LIMIT，以SQL CASE WHEN octet_length<=1MiB THEN authority_data ELSE NULL END返回payload；与第一阶段每行outer与size对应，并再次限制总预算。4表总512上限及8MiB是明确拒绝门，不分页假计数。原case_count按全部case修订；disposition_counts按全部保存prepared/frozen修订，不distinct、不改经营完成数。DTO上限1MiB。连接使用原只读租户设置；事务内先SET LOCAL statement_timeout='3000ms'与lock_timeout='500ms'，均固定字面量，不绕过连接角色；超时整视图稳定失败。最多9个SELECT，事务总耗时另以monotonic 10秒门在查询间检查，超时不继续payload。

## 真实性、关系和输出

每行raw完整字段、strict bool/int、时间带时区、payload tenant、outer identity/revision/hash/time与模型一致；使用原模型请求重建与canonical_hash，拒绝缺字段/额外字段/隐式coercion。所有对外字段执行现有只读隐私门，敏感原文不得进DTO或错误。底层SQL错误统一稳定unavailable，不回显SQL/DSN/row。

Case核原CreatePriceCaseRequest hash、revision1/open原producer形态；未证明writer的stale/closed拒绝，不猜签名。Contract核request+REQUIRED_GATE_TYPES+externalEffectCapable hash。Disposition核exact case/contract resource/id/revision/hash、target包含关系、canonical gate集合和类型；receiptId仅是保存字段，沿原Store exact lookup语义，不新增伪造receipt authority。prepared必须rev/version1、无prior，重建typed request算binding与原prepared hash；frozen必须exact前版、rev/version递增、所有继承字段相等，按原七排除字段完整payload算hash。stale无原producer证明则稳定拒绝。

Observation重建原request、核hash/派生ID/revision1/outer observed_at，exact引用已验证frozen disposition，复用kind→receipt type/outcomes纯规则与原unknown/manualCase模型；不要求等于全局latest disposition。历史receipt/budget/gate/approval refs只作保存事实，reader不调用gate resolver或receipt consumer，不伪称当前批准。

用已验证三list适配原contribution_view以保留原业务计数/阻断顺序；显式allowedCommands=[]、repricingEnabled=false、externalEffectsAllowed=false。空成功只在可信snapshot确实空时产生0；任何读取/校验/限额失败稳定非200，不沿原service补空分支。保留真实缺口与unknown，不删除阻断换视觉通过。

## 门禁、验证与回滚

先冻结原producer/Store/DDL/本方案与probe，独立Prime route PASS合法消费后才写产品。RED覆盖原GET404/失败假0风险、新reader不存在、四类prepared+frozen计数、跨租户/外层漂移/typed hash/祖先继承/观察指向旧frozen、未来行、限额在payload前拒绝、SQLCASE、隐私与无命令。

最小实现后专项/原W6-06与research/root只读累计；原w6_006隔离PG正常producer行、snapshot并发、RLS/FORCE、25006、超大payload门；独立quality。通过后精确提交，再fresh维护Task/controller质量门和新意图更新API；原真人SDK、query400/anonymous401、原650表完整指纹不变、适用三视口原稿及livePrime，准确Delivery/Authority七强同步。

回滚只撤回本GET installed专用reader路由及本次纯规则无行为提取，服务版本切换仍需fresh维护门；不reset/覆盖用户改动，不迁移原库。API读波不代替每日/每次aos最新同权威卷完整PG→API→Web。全部经营首链、真正用户最终预算、安装全生命周期/八场景/视觉/连续观察发布保持未完成。
