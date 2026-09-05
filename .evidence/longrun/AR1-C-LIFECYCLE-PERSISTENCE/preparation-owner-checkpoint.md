# AR1-c 准备资源所有者内部检查点

日期：2026-09-06。基线75429e22 / AOS-000519；m1串行，AR1-c仍进行中，新增业务场景0。

- 新增PreparationOwner，可信签名会话组由平台task持有，等待方取消不传播到后台；只返回提交结果，不返回invoke会话。停止、进程退出、租期到期收敛清理。
- Red：模块缺失；补充立即stop及stop清理跨lease反证，2失败6通过。修正启动前取消及清理计时器边界后8通过。Prime发现子任务drain仍受timeout及异常吞失，移出计时器、_settle等待并保留异常，新增两个组合测试，共10专项通过。
- 真实signed_owned复用实际临时签名Registry、OCI digest、完整临时PG安装历史和commit_prepared；prepared返回后独立inspect容器running且账本未释放，stop后精确容器不存在、账本released、binding为0。原正常/撤销联合仍通过：3项16.52s。
- 累计命令：AOS_EXTENSION_OCI_TEST=1 AOS_EXTENSION_PG_TEST=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest --noconftest services/aos-api/tests/extension_runtime services/aos-api/tests/asset_registry/test_manifest_contracts.py services/aos-api/tests/asset_registry/test_manifest_loader.py services/aos-api/tests/asset_registry/test_signature.py services/aos-api/tests/asset_registry/test_installation_service.py services/aos-api/tests/asset_registry/test_installation_revalidation.py services/aos-api/tests/asset_registry/test_release_policy.py services/aos-api/tests/asset_registry/test_canonical_hash.py services/aos-api/tests/asset_registry/test_control_wiring.py services/aos-api/tests/asset_registry/test_installation_evidence.py -q --tb=short
- 结果：400 passed，6既有warnings，67.53s，exit0；既有JDBC退出日志closed stream仍存在，不影响本次退出码，不声称整个API无告警。diff check通过，专用引擎仅剩aos-ar1c-pg。
- Prime独立只读复审：原两处已修，无新增实质问题。无页面改动，浏览器N/A；非完整worker、不是重启恢复/active/enabled或真实业务授权。
- 后续：未领取资源意图取消与已领取未知结果区分、持久worker领取/失败恢复、健康verify、正式权限/策略/broker和全生命周期；AR1-c完毕才进入AR1-d UI及业务后续。
