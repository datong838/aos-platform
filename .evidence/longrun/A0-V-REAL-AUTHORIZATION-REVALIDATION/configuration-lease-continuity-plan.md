# 配置切换期续租与延迟启用修复方案

基线 462baceb。实证：配置 succeeded 后 observed_state=unknown、disabled/fenced；续租 ready-only 拒绝导致 Host 在 03:27:24 UTC 退出。启用仅 accepted，不得声称成功。资源释放后禁止复活，后续正式恢复新代际。

文件：services/aos-api/aos_api/extension_runtime/lease_renewal.py、enable_commit.py；对应 tests/extension_runtime/test_lease_renewal.py 与延迟启用回归。新增逻辑前先写失败测试。

续租继续要求 active 安装、同一 package lock、已成功 runtime-apply、同代资源完整存活未过期、当前权限及 schema/platform 条件、真实即时健康。仅对 fenced/not-enabled 的配置切换态增加窄分支：unknown 必须 desired=disabled，且由同租户同安装同 generation 的 succeeded configure 的不可变 configuration_committed 事件证明当前 configRef 和 bindingRevision，事件 hash 必须匹配；draining 可保留重配置前的 desired=enabled，但实际 enabled 必须 false；必须来自当前未过期 configure fencing 及其 exact accepted target，并且 bindingRevision=accepted+1。续租不修改 enabled/observed/fence，不给予业务调用权限。未知、事件缺失/篡改、其他代际、其他控制类型、released/expired 仍拒绝。

启用使用当前 enable deadline 和真实资源租约 deadline；已成功 preparation 的历史执行 deadline 不再作为运行时有效期。保留 preparation 必须 succeeded 和同代真实资源核验，当前权限/配置/健康/最终时效全部保留。过期 enable 或 lease 仍拒绝。

验证：失效场景先红再绿；原负向测试不回退；加入旧 preparation deadline 已过而新 lease/enable 有效的正例、过期 lease/enable 负例。完成后正式恢复再验证配置→等待跨续租→enable，不在产品库修改 deadline/state 来造场景。
