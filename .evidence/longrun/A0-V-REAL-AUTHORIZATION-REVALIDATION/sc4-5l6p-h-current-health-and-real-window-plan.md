# H当前健康与真实首链诊断窗口

## 目标与范围
H已正式接管core组17，原G完整退休；不再重装、不重发G旧unknown。使用已有模型4/route4/policy5、Logic2/Skill3及8个当前r3绑定。新增scripts/a0v_h_current_binding_refresh.py只调用既有Owner服务刷新当前健康和依赖证据，保持模型/Skill/角色身份与历史不变。先全部校验8个绑定及依赖，再capability suspend/evaluate/activate及Skill evaluate；每步意图/回执，未知不重发。真实Provider探活后才执行，无虚构健康。

新增scripts/a0v_h_product_window.py作为原已验证权威/策略/启用/源运行程序的固定H profile；前序必须G第二窗口真实selection/control/policy4回执，后继H policy5绑定现有Case当前版本。H入口expand从17到18，权限/审批由原Lifecycle复核。只运行一次源schedule，finally关闭；自然Host消费，不手造Run，不注入handler。

测试覆盖当前r3身份/依赖拒绝、未知意图拒绝、H各profile身份与独立目录、旧policy4 exact链、group17/18。业务成功需要真实Run与后续产物证据；单次源成功或注册GREEN不算。

复核后补充最小profile扩展文件：scripts/a0v_event_complete_product_authority.py、scripts/a0v_event_complete_product_source_once.py新增默认保持原G行为的preflight_profile注入点；scripts/a0v_event_complete_product_enable.py将原组11提取为默认常量，H固定17；新增scripts/a0v_h_product_preflight.py明确H create/resume来源。原G/F脚本默认行为与历史路径不变，避免全局替换模块影响原流程。H不提供历史失败恢复重发分支。

07:06范围校正：SourceSelection/RuntimeControl是installation+generation内的修订链，H首版必须previousRef=None；不可把G第二窗口引用作为H前序。原selection被Owner拒绝未落库，旧H authority意图保留，v2新目录/key创建H首版。跨安装延续的是业务Case/Policy4→5及schedule binding CAS历史，不是混用源权限修订链。补测试明确两个源authority previousRef为空。

## 07:09当前事实
真实模型探活成功（59 tokens），8 capability与8 Skill3绑定经Owner刷新，ResponsibilityPlan2 ready/complete/blockers=[]。H authority-v2 prepare/selection/control/binding，Policy5 prepare/approve/put，event入口approve/expand/control approval/enable均已通过；core17→event18。正在执行单次真实商品源更新与180秒自然观察。原默认G profile回归及H新增测试累计32通过，校正source权限代次后针对回归20通过。尚不宣称Run成功。
