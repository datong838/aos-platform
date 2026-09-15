# SC4-5l6m F/growth 1.9 固定配置验证

Rules：m1、方案先行、最小更改；旧 A–E 脚本未改、不 push、230 L0 挂起。

方案 434adbb7；Task SC4-5L6M-GROWTH19-PROFILE-20260916。

新增独立 F profile，状态目录与签名根指向 20260916/growth-1.9-current-package。固定 E ID 与 generation；每次观察 E 都检查代次，disable-e/settle-e 再检查入口。create-f 复用 replacement_ref 并要求唯一 detached 生命周期记录和 E 分派数 0，备份后写独立 immutable intent，固定 growth 1.9 与 F 幂等前缀。

负例先发现 disable-e 未拒绝 E generation 漂移（1 failed、17 passed），随后补入口与底层观察保护。F profile + 历史 current_reinstall + current build profile 三文件最终 35 passed、7 既有警告，0.16 秒，退出 0。新脚本 observe 无写成功；真实 E 仍 active@5/ready/enabled，epoch3/revision6，canary0。diff check 通过。

范围：本步只读主库；未调用 disable/create/prepare/configure/enable 等写阶段，尚未证明真实 F 安装成功。下一波：内部 Registry 签名发布与备份校验，再按固定 E→F 生命周期记录每一步，必要时补三个独立事件分派审批的执行器。发布决策和真实八工作台经营闭环仍未完成。
