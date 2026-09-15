# SC4-5l6m growth 1.9 的 F 安装配置

Rules：m1、先方案、最小修改，保护旧 A–E 记录；不 push，230 L0 挂起。

基线 b9e4cd37。新鲜只读 E：1c08edfb-ec0d-4abb-a411-7b6ec0d6066a@5，generation ebaa620a-8831-4c2a-b971-788383f352f8，binding revision 6、epoch 3，active/ready/enabled/unfenced，canary 安装 0。签名前置 PREFLIGHT_GREEN，outputTreeHash 4756ec28f4d7cc4c8670c572df5b0c0e7f1b6ac33e1882c89d2a6bc0e66dcd2c，Registry/安装/环境写入 0。

新增 scripts/a0v_ecommerce_growth_1_9_reinstall.py，不修改历史 current_reinstall.py 的 A–E 行为。F 状态放 .aos-recovery-20260916/state/growth-1.9-current-package/install/f，复用旧只读观察与生命周期服务配置能力；固定 E 前序身份，独立 F 幂等前缀和 1.9 坐标。F 创建前必须满足旧 replacement_ref 的禁用/资源已释放/无未决操作，并额外确认 E 对应 resumed activation 已有 detached 生命周期记录且不存在指向 E 的分派。

阶段：observe；disable-e（走 ar2_017）；settle-e；create-f；prepare-f；verify-f；stage-f；configure-f；enable-f。创建 F 前备份数据库，意图与结果只创建不覆盖。结果未知时先读 Receipt，不自动重发。新 Registry 必须先有资格通过的 1.9 包；脚本开发与静态/无写测试通过前不执行写阶段。

新增 tests/extension_runtime/test_growth19_reinstall_profile.py 验证固定身份/坐标/状态目录、前序排空拒绝、非法标签及三阶段调用路由；真实 E→F 操作另落证据。之后还要接 F 的独立 cutover/事件入口审批及完整真实业务首链，不能把配置脚本当成产品完成。
