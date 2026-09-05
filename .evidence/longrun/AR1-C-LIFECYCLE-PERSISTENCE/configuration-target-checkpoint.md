# AR1-c 配置请求精确目标检查点

2026-09-06，m1 基线 e8bdd7ce / AOS-000529，主生命周期 Lease 持续有效。

实现 ConfigureTarget / ConfigurationRef 严格不可变引用；configure accept 保存 exact generation、binding revision、configuration id/revision/hash，完整幂等哈希、不可变 accepted 事件及 outbox 同事务提交，填充既有 expected_binding_revision。新请求重验 TenantScope/绑定 CAS/deadline；重放比较完整请求后返回既有操作，不重复执行。其余原操作哈希不变，无新增迁移。此处不验证配置存在或授予权限，不开启 binding、业务端口或创建默认配置。

验证：新增18项Red（缺参数/校验），初次相邻67项通过；加入dict行工厂后累计547 passed / 6既有warnings / 93.23s / exit0。独立Prime发现model_copy/model_construct对象可能绕过重验，新增三项反证全部Red，两层启用revalidate_instances=always后最终配置及相邻71 passed / 14.71s / exit0。累计547在该修补前运行，不能称最终代码全量重跑。git diff --check通过。

环境仅专用18432临时schema及隔离OCI，不用共享业务库，不访问Provider、不产生费用或发布。后台代码无页面变更，未重载在线API，不把旧浏览器冒烟当本代码验收。新增真实业务场景0，AR1-c整波未完成，历史44/81不变。

下一段：从已持久化请求读取并验证目标，将配置更新fence严格绑定请求代次/CAS；随后接不可变配置权威、排空提交及启用前置。耗时可实测部分：首次Red8.09s、相邻14.64s、累计93.23s、复审反证7.06s、最终相邻14.71s；不估算网络/思考占比。
