# 栖月汇当前配置恢复输入核对（2026-10-11）

本记录属于qyh-full-system-restoration-20261011；范围仍为电商域、栖月汇商贸有限公司org-org/dev-project。目标是新安装的正式配置恢复，不重启旧计划或继承旧执行权限。恢复库aos_meta_head@a0v_159保留647表；原库与所有历史实例保持。

## 实测结果

三个历史安装的ConfigurationDocument均经原解码器验证不可变hash；各有角色、数据、预算、运行策略四类引用。此数量不表示八工作台或正式八配置已验收。三者binding均disabled/fenced，配置及binding元数据在只读事务内精确保持。

| 历史安装 | 运行策略引用/当前头 | 角色/数据/预算Ref | 说明 |
| --- | --- | --- | --- |
| ef5bc0c3-1dbe-4659-b839-2350f70232bf | 5/13 | 各自匹配当前头 | 运行策略过旧；旧包来源亦不满足当前四版本 |
| 89975129-7e0f-4860-ac56-7a031ebe4a1a | 12/13 | 各自匹配当前头 | 运行策略过旧；不能从当前Schedule关联为空推出旧12Run已收口 |
| 407059df-6f1f-4927-acd7-8e388692838e | 13/13 | 各自匹配当前头 | 引用较新，但有关联旧Schedule/Run，不是可直接启用的空白安装 |

当前运行策略13的五类依赖引用均匹配精确当前revision与contentHash。其中network/egress/dataClassification/quota当前有效且active；budgetPolicy13为active但已于2026-09-25T02:52:33.666717Z过期。不能通过改旧有效期、换actor字符串、复制旧配置或关闭准入门修复。

407安装当前关联12个停用Schedule，保留65个Run；每个Schedule各1个Run的executor_stopped并非TRUE，合计12个。此值只表示缺少停止证明，不等于证明进程仍运行，也不证明就是历史原12Run。其余两个安装当前关联为空只是最新关联路由结果，不能认定旧Run已退休。三个安装operation的历史succeeded标签也不代替当前资源、身份或执行终止证明。

## 恢复输入与下一原流程

1. 已授权整套恢复继续；无需重复要求整套审批。等待已提出的独立真实发布账号信息，完成core1.4.3、Growth1.13.0原Registry职责分离发布；现有平台1.23.2、operations1.2.2保持原published来源。不能冒充或伪造第二发布者。
2. 在正式当前身份与Owner核对后，经原安装路由创建新的当前四包安装；不启用这三个历史binding、不绑定旧Schedule、不重放Run。目录展示与业务执行分别验收。
3. 复用精确来源作为恢复参考，而非权限。预算策略需由原策略更新/审批流程形成新不可变revision与真实有效窗口，运行策略再引用该新revision；不得自动续期历史审批。随后原四Source及当前配置权限reader在正式调用方事务中验证。原reader含FOR SHARE锁，本次只读元数据调查没有调用它们，不声称完整准入通过。
4. 当前正式身份、Owner、八配置及审批预算齐备后才启用对应Host/worker/Provider。API/Web及八页面按各自正式门验收，不以数据卷加载、历史配置可解码、镜像诊断或文档当作全系统恢复完成。

## 证据及限制

restored-current-configuration-audit.json：真实原解码、四类Ref当前头及历史预算窗口。

restored-configuration-dependency-audit.json：当前策略五类依赖有效窗口、三个安装operation汇总及最新Schedule/Run关联。全程有限LOGIN、READ ONLY/REPEATABLE READ、零数据库写、零商城源读取、零业务payload读取、零旧执行器调用；没有新增任何业务权限。

依赖调查初次误用了ConfigurationRef的hash字段读取VersionedAssetRef，原SQL只读、尚未落盘结果即失败。依据实际原契约改为contentHash裸hash后调查成功；没有重放外部效果或改准入规则。尚未完成：独立发布、当前新安装配置、正式身份/Owner、API切换、Web八页面及自然首链。
