# 配置引用可复用与失效面

2026-10-11T06:28:54Z，原cluster/aos_meta_head@092，READ ONLY。

精确安装97aeb2e7-59ba-40f6-89a3-fb0293bc0497、代际3a445eee-aa28-4459-9e5a-f12a806a94b1，配置721433ba-5256-4b12-9043-0bcfab658bf0@1通过当前原ConfigurationDocument严格解码及configuration_store._decode全封套哈希。没有复制哈希算法、actor/正文输出或正式权限读取器执行。仅证明该历史配置格式与封套哈希兼容，不证明完整schema/运行兼容。

引用读回：责任计划revision2、数据分类revision1、预算revision1均与历史库head revision/hash一致；数据分类当前时效有效。预算只核列hash/lifecycle，没有完整内容及使用额授权认证。

明确拒绝面：配置运行策略引用revision4；历史当前head为revision13且hash不同。原_load_runtime_policy要求current exact，不能自动换成head13。旧策略引用预算策略revision4截至2026-09-14T07:02:28.449303Z已过期；预算策略head13截至2026-09-25T02:52:33.666717Z也过期。二者lifecycle均active，但active不是时效有效。

原生产授权读器含FOR SHARE/FOR UPDATE，未在真库调用；本次诊断使用只读SELECT列核验，与正式事务锁/当前权限/所有来源正文认证有严格区别。查询分别独立快照，当前159仍为空安装配置，不继承旧库任何执行许可。

方案一致性：231-3 configure/enable必须重验精确来源及批准策略；231-9已说明预算策略过期。结果支持保留历史材料、重新登记合规当前配置，不支持篡改旧版本有效期或复制active/config_ref。正式恢复前还需制品签名、迁移兼容、身份/Owner/Host当前持有与健康及八配置完整验证。

后续安全登记：准备旧库092到当前159的恢复兼容清单及隔离全库恢复演练，保留源数据/旧12Run不执行、所有执行门关闭；仅在正式维护窗口和独立恢复授权下处理当前库。名称恢复的一次授权仍待回复，不重复提问。
