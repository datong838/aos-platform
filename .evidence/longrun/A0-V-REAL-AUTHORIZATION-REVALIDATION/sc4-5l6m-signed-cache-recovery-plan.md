# 签名目录运行时缓存污染恢复

Rules：m1 单写、先方案、最小改动；不 push，230 L0 挂起。

基线 eac6451b。growth 1.9 Registry apply 在 signed_tree/read_all(OLD_ROOT) 失败，未创建新签名树、未发布、未修改安装。16 个历史制品中仅 growth 1.8 签名 invalid。临时副本仅移除两个 2026-09-15 23:51 生成的缓存文件后，原签名验证 valid，contentHash=sha256:ac3b80551ca9325b69853d10f41d61134fe4c0a3f8ebcf83c0343deb0147bd5f。

文件为 backend/ecommerce_growth/__pycache__/ecommerce_business_investigation_case.cpython-311.pyc 和 sdk_ports.cpython-311.pyc。既有 __init__.pyc 属于已签名历史字节，必须保留。不得忽略签名范围、重签历史版本或批量清理 pycache。

修复 scripts/a0v_qyh_current_product_event_first_chain.py 的 setup：将签名包路径加入 import 路径前关闭本 CLI 进程字节码写入。测试使用临时签名包路径和提前停止的 preflight，执行实际模块导入，验证不产生缓存。先红后绿。

恢复先备份两个缓存及哈希、目录清单；精确移出两文件到独立隔离目录，复验全部 16 个包原签名。若复验失败则恢复原文件并停止发布。复验成功后再执行原新 Registry 流程；输出不覆盖，安装 E 保持原状态。本操作不改变签名源码或历史签名。
