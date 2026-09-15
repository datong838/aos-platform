# SC4-5l6m 扩缩后正式退役组合

Rules：m1、方案先行、最小测试修改、隔离 PG、不 push、主库不变、230 L0 挂起。

方案 26824167；Task SC4-5L6M-RETIREMENT-20260916。

真实 PG fixture 经过 prepare/commit/validate/resume，随后同安装代次 expand/fence/shrink，最后原 RuntimeBinding fence 与 ar2_017 dependent disable/detach。组版本累计 +5；九项恢复 legacy，安装引用为空、fence=false；claim gate 删除。重复 detach 同 Receipt 回放。

专项 1 passed；生命周期两个文件累计 22 passed、7 既有警告，3.61 秒，退出 0。只新增测试，无生产桥接放宽。fixture 的审批与安装来源不等于真实 Service 签名审批或真实 OCI 卸载验收。主库 E 保持不变。

下一项：使用标准临时 _ti4_test 数据库完成既有 ProductEvent 审批 PG 测试，再验证完整 EventControlDispatchLifecycle Service。此前部署审查的 exact fence、同步互斥、异步排空、扩缩后退役四项已各有明确证据；整体新版本部署与业务验收仍未完成。
