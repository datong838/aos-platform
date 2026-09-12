# Niushop 1.5 商品快照候选验证

2026-09-13 03:10；基线 ce8cfe96，m1 单人串行。

新增 prepare_niushop_product_candidate.py 与候选 bundles/candidates/ecommerce/platform.ecommerce.niushop/1.5.0。v2 增加显式 validation.non_negative，保留原价款约束；旧 v1 不变。新增约束测试先红 2 failed/32 passed，再修正；最终候选、v1/v2 联合 69 passed，4.14 秒，7 项既有 warning。

实际创建候选后的独立回读：旧 1.4 树 hash 仍为 sha256:e819116f16f2c0e057fbbbbbcfba05e614ddafb2f312566c24dc07cb15244709；新树 sha256:e25d7e781db3b03b72cf8443167d9536b2b1e9aad01aa385e4cd96d0ad4edfec。仅 bundle.yaml、P02 mapping、bundle-evals.json 三文件不同。重复 prepare 在修改前拒绝，旧树保持不变。P01 mapping hash 保持不变；Product 28 列、10 项静态评估通过，源状态/删除/源时间及负金额约束未被丢弃。

初次静态准备时 API 导入加载了 dotenv，未调用数据库或源读取；准备工具现显式禁用 dotenv，重新只读评估通过。评估使用 synthetic 值，不能代替真实商品数据验收。

AR2 ar2-7 闭包 1809 scanned /158 classified /93 migrated，五类错误均空；git diff --check 通过。审查符合本波方案：当前签名 1.4 根、Registry、安装实例、来源调用额度和线上数据均未修改；API 未加载新增 v2 代码。候选尚未构建/签名/安装，P02 真实读取、P03 关系、自然事件消费者和八工作台业务未完成。

下一波：增加隔离的 1.5 构建 profile，经实际 OCI 构建与隔离资格验证后准备 append-only Registry successor；升级前核对当前安装和源 schema，保持原 1.4 不变。后续正式 P02 图、当前审批及一次受控读取，不能绕过产品 Owner 或手工注入 Case/Run。
