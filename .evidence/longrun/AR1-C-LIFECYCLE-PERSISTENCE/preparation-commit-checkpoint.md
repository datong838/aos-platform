# AR1-c 安装准备原子提交检查点

2026-09-06；基线9e8c9446，当前仍AR1-c进行中，新增业务场景0。

新增commit_prepared可信内部事务：当前权限、ETag/操作CAS、原approved与registered、Registry全部lock成员签名、同代精确资源集、真实container ID登记及当前claims hash逐项核对。committing→Installation applied→关联证明事件→succeeded同事务；无active指针、无enabled/ready binding。backend成员不完整、纯前端runtime无独立准备观察时拒绝，不伪造完成。

Installation新增runtime_preparation证据和专用追加方法；旧dry_apply严格不变、旧证据JSON字段及canonical算法不变。operation的preparation_committed事件关联安装证据ref/hash、revision、generation、lock和资源摘要。相同提交重放不追加；安装已后续推进则要求读取当前操作。

Red：新增12项首先因实现缺失失败。Prime发现资源循环后的到期窗口；延迟注册查询跨越150ms资源有效期时原实现错误提交，反证DID NOT RAISE。修复在committing前和succeeded前统一复验最早资源/操作截止；反证转Green。

专项最终覆盖20个真实独立PG安装历史场景；含合法旧dry_apply制造版本漂移、操作CAS、缺少/额外/异代/异hash/claims变化、过期、权限/签名撤销、无注册、已释放、invalid证据、故障回滚、重放。该PG安装夹具的Registry检查器明确为测试替身，不算签名运行包完整安装集成。旧verify对runtime的拒绝另有独立InstallationRevalidator反证，联合全链仍下一任务。

累计命令：原extension_runtime与asset_registry指定回归集合，新增test_installation_evidence.py；AOS_EXTENSION_OCI_TEST=1、AOS_EXTENSION_PG_TEST=1、--noconftest，独立18432临时schema，未迁移共享库。结果387 passed、6既有warnings、60.16秒、exit0；既有JDBC退出日志提示仍存在。默认引擎desktop-linux保持不变，专用引擎只留aos-ar1c-pg。

Prime只读复核确认到期窗口修复及事实限制。无页面/API入口变化，浏览器不适用，不冒充浏览器验收。下一步补签名Registry/真实OCI/完整Installation联合准备链和旧verify拒绝，然后正式worker、策略/broker与完整生命周期；AR1-d界面尚未进入。
