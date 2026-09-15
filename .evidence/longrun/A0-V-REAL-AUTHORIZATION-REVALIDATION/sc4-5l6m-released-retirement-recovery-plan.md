# Host 停止后 resumed 安装正式退役恢复

Rules：m1 单写、先方案、保留原迁移/原 Receipt，不 push，230 L0 挂起。

真实证据：E 第一次 settle disable 360a4d20-9a14-4fa5-a1b2-3dab51863afa succeeded；当前 binding revision9/epoch5、disabled/fenced、资源released。activation b5555da7-6d0e-52f8-a443-d39b8264f40c resumed，生命周期记录0、指向E分派9。F在require_detached_e拒绝，未创建。原Python限定 b.revision=activation.target_runtime_revision+3、epoch=activation.target_execution_epoch+1；Host停止额外推进版本后静默返回None，导致禁用成功但入口未脱离。

修改 services/aos-api/aos_api/ecommerce_growth_lifecycle.py：以本次真实 disable operation 的 expected_binding_revision+1 验证 fence，而非 activation 固定偏移；仍限定同租户/安装/代次、resumed、未启用/已fenced/draining，当前epoch必须严格大于activation epoch。若存在指向该安装的分派却无法找到唯一合法activation，拒绝而非静默成功。

新增 services/aos-api/alembic/versions/a0v_055_released_growth_retirement.py：替换 ar2_017 fence/detach 两受控函数中的 epoch 等值假设为严格前进；保留本次 disable exact CAS、actor、当前阶段、snapshot、claim gate、非特权角色和收据守卫。检查同代次全部epoch的claimed/unknown异步工作，禁止旧epoch之外的未决工作被遗漏。用新增迁移变更已部署函数，不改原历史迁移。读取旧函数定义时精确校验被替换片段次数，漂移即拒绝。

新增真实PG用例：正常resumed；额外停止fence/曾完成disable后再次合法disable；epoch未前进、分派漂移、claimed/unknown任意epoch拒绝；成功detach回放、9入口legacy、claim gate释放。先复现原逻辑返回None再修复。部署前新增独立备份恢复验证，旧disable Receipt不改写；新命令使用新幂等键/current CAS执行正式disable，绝不直接更新业务分派。F只有exact detach成功后可创建。

部署执行文件新增 scripts/a0v_released_retirement_deploy.py，固定 a0v054→055、独立 .aos-recovery-20260916/state/released-retirement-deployment 与 aos_released_retirement_20260916_test，沿用540表指纹/备份恢复/lease/不可覆盖意图检查。增加函数定义验真：epoch严格前进、保留exact CAS、全代次未决工作拦截。已有054执行器与证据不改。E已disabled，无需为部署再次改变其状态；若后台仍造成指纹变化则停止并诊断。

部署并重启Host加载新代码后，新增 F 配置动作 reconcile-e：只接收固定E已disabled/资源released/无未决运行操作、仍有唯一resumed activation和9个E入口、无生命周期记录的精确恢复状态；以当前binding CAS提交新disable命令，生成新Receipt，不覆盖第一次disable结果。该动作需独立测试及记录。
