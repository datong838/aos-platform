# SC4-5l6l 第 2/6：growth 1.9 OCI 构建与资格

日期：2026-09-16；代码基线 `1128d389`；m1，不 push。

current 四包 profile 只把 growth 1.8 升为 1.9，Niushop 1.23、core 1.3、operations-base 1.2 保持。9 项 profile/successor 测试通过。

真实隔离 OCI 构建 `BUILD_GREEN`：4 包、3 runtime、8 模块、14 operation；输出树 `sha256:4756ec28f4d7cc4c8670c572df5b0c0e7f1b6ac33e1882c89d2a6bc0e66dcd2c`。growth 源树为纠正后的 `sha256:6c27c24ae96bc2cb013526e2f431d3ee2d2fdb6925e0b3729f6a6e12c3c4472f`，构建 content hash `sha256:b52eb830e85d9fb3bc2353de59c460109e0040e01466c94dad54fd5a6db6c364`。

`QUALIFICATION_GREEN`：三个实际 OCI session 分别精确注册 1/2/25 项，各完成 2048 次心跳并 released；growth 只读探针仍为 1 Case/1 Run、executionAllowed=false，七类篡改全部拒绝。Registry、installation、Provider、外部发布变更均为 0，资格临时签名未持久化。

下一步第 3/6：基于当前 16 版本签名根追加 growth 1.9 为 17 版本 Registry successor；先 dry preflight，再签名发布，主安装仍不变。
