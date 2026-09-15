# 签名缓存污染恢复验证

基线 bf3cf363。实际模块导入测试先 RED：生成 signed_cache_probe.cpython-311.pyc。setup 在加入签名包路径前关闭字节码写入后，该测试及首链脚本原测试共 13 passed、7 既有 warnings。git diff --check 通过。

实际恢复仅隔离方案所列两个额外缓存。私有证据位于 .aos-recovery-20260916/state/growth-1.9-current-package/registry/signed-cache-quarantine/{before,result}.json，保存原缓存、SHA256 和全部 16 包内容哈希。原签名全部 valid，未重签、未修改源码或既有已签名 __init__.pyc。失败自动回填分支未触发。

这是历史制品恢复及本执行器防污染修复，不代表 growth 1.9 已登记、安装或业务验收通过。下一步继续原 Registry 登记波次；E 未执行禁用。
