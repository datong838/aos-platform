# 方案与代码复审

新专用MediaGateSourceResolver完整参数为原conn/原scope/原RegisterMediaGateProfileRequest，包含manifest/signature/policy三ref和四Rule/gate definitions；Stage callback未修改，仍专用于原Stage入口。
无Media resolver时连接前拒绝；resolver返回非精确True时原事务退出、未进入_replay/_require_review_rule/INSERT/_receipt。未知异常不隐去、不降级，不产生自发重试。完整验签/发布/当前安装和撤回必须由下一原Registry/Producer实现，不把同一conn注入本身当验签证明。

RED9失败后最小生产diff通过9新单测及原四门/原W2a/W2b累计，共39PASS/0skip/7既有warning。新测试是调度接口double，接受True只允许进入原路径，不伪称签名authority；原W7 fixture明确test-only callback，继续验证原四门持久登记/报告/租户行为。全部测试原autouse只创建并清理clone18431上的独立aos_test_*库，未操作当前18446业务库/Host/Provider。

原router未配置专用恒True，媒体保持fail-closed；整个Source正向尚未收口。未改原业务阈值、四Rule spec、策略、包/签名、安装、真实配置、Store schema、登录、发布身份或旧Run。源码候选未切现有服务；页面无改动，不用浏览器空态加验收。原22用户修改仍保留。
组件修复准确对应原media-source-wiring-review第1步接口缺口，后续第2～4步原Registry、Source producer稳定ref、签名贡献和真实正负门仍需完成。完整Goal/恢复/Source父Task ACTIVE。
