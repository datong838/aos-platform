# 当前157→159原卷重启维护方案

唯一写者01a107a2-e9e4-7670-bc44-1144fa9b27e2，m1 fa70a7123，authority1699。用户已授权最新全量重启与安全迁移；原PG9cc6091c、卷aos-a0v-recovery-pg-data、cluster7683855731447750695，当前库aos_current_preview_20260927@157。Desktop研发库不替代该权威卷。

先全schema只读清册并冻结当前提交源码及迁移依赖hash。旧150全备校验器拒绝私有schema，禁止猴补丁放宽。新增本目录snapshot_all.py和test_snapshot_all.py，独立全schema行摘要、函数/触发器/FK/ACL/角色/序列/策略/默认权限/扩展目录比较；数据留私有state，公开报告仅hash与数量。先RED覆盖私有schema同名表、防SQL注入与遗漏。

再新增capture_restore157.py：第一份一致快照备份/globals/TOC，独立新none-network PG卷全恢复并精确比较，保留所有卷备份。迁移源码冻结于提交HEAD，不带未提交产品修改。原158闭合存储与159Judge预算全部原事务演练，旧数据不变、新对象权限保持封闭。

之后单独追加current_window159.py计划与测试：停止精确API/Web、原PG listen空并排空client/prepared，第二可校验一致备份、新副本完整恢复与两步演练全部通过，才原卷逐步158→159；每步intent/terminal/after-version独立落盘，未知不得重发。恢复原配置、同卷PG→最新提交签名API→Web，核版本/身份/八页/tenant/canary/禁入。Host/worker/Provider保持off，不读商城源/旧12Run，不push。全备/全恢复/迁移/浏览器未完成时Task不Delivery。

## 首次恢复已知失败接续
首次私有state current159-first-05b88779fad3，目标current159-first-1579cb9f5251。角色导入命令terminal非零且No such socket，未连接；只读确认当前唯一非系统role aos_app、目标库不存在。禁止重跑capture_restore157.py。新增resume_restore157.py只消费固定首备与失败、独立journal，重新检查空目标后执行角色导入与全恢复；native_snapshot159.py在冻结迁移工具镜像的none网络/只读socket内以原生REPEATABLE READ采集完整副本，再精确比较。比较差异只诊断，不宽松PASS；旧失败/副本/备份不删。

全恢复两命令已各terminal0；只读比较工具创建因Colima未挂载当前宿主仓库路径而失败125，未连接数据库。禁止重放角色/恢复。新增compare_restore157.py，仅固定已有副本，使用冻结工具镜像none网络/只读socket，Python源码经stdin只读传入并绑定SHA，避免改变Colima全局挂载；独立原生只读事务比较已恢复库，保留原创建失败容器。

## 精确目录差异复审
原生副本615表/410函数已读取，全部行摘要、函数体、ACL、角色、序列当前值与原库相同；仅constraints/triggers存在差异。18个CHECK为原已审长度/AND结合律表达式；2756个内部RI触发器名称随恢复OID改变。新增restore_comparison.py/test_restore_comparison.py：复用原150已审严格length_and_candidate，其他CHECK不归一；只允许tgisinternal且名字严格RI_ConstraintTrigger_[ac]_[数字]、完整定义中原名字精确匹配且RI_FKey原生函数在闭合清单的名称变化；保留重复事件多重集和全部属性，不删除触发器。数据/ACL/函数/触发模式/约束变化必须失败，原差异完整留私有state。此审查不是158/159演练或第二零窗口备份通过。

原150严格规则仅覆盖15个public CHECK；剩余3个为私有deployment_anchor.publisher_subject/signer_key_id/signer_publisher的长度1..200与btrim合取。逐项冻结schema/table/conname、列名、上下界和唯一两种原/恢复表达式；仅允许括号合取结合变化，操作数、NULL三值语义和所有约束属性不变。不得扩大旧150规则或全局接受bound200。新增负测改变200/操作符/列名/所属schema必须失败。原18全部已审的提前文案以此明细纠正；旧结果保留，不能宣称第一轮归一已经通过。
