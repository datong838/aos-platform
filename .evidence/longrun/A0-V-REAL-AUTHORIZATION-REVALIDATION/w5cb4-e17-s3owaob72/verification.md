# b72 同key重放与回滚第一段验证

原同key实际RED：1 failed/7 warnings/14.49s，B72_SAME_KEY_REPLAY_ADVANCED_EPOCH；保留replay-original.txt。候选新增AOS_B72_LICENSE_REPLAY_PROBE，必须配b71及合法b70顺序，仅两个测试文件。先FOR UPDATE exact epoch行，再按tenant/operation/key查看Receipt，存在时不UPDATE epoch；原Store继续校验request hash。scope仍由原connect与RLS处理。

候选撤销先1 passed/7 warnings/14.89s；评测先1 passed/7 warnings；原b71撤销先、default各1 passed/7 warnings，节点23.67/23.40/23.32s。两顺序保留40001/Receipt0及精确PID等待/后续42501检查；新增同key两次epoch/event/原Receipt均(1,1,1)，新key错hash、commit抛异常均回滚epoch及新Receipt为0。强制错误发生在已有撤销事件之后，因此**没有证明首次新事件插入的回滚**，不扩大结论。

编译及git diff --check通过。测试后历史aos_test_*_ti4_test库49，与b71结束49相同，本波未在启动前重新计数，不宣称逐节点前后全量对账。查询第一次使用不存在role aos被拒，改用既有测试role后只读完成。只使用test-only5433，不改当前135库、生产Store/迁移/Host/worker/Provider。

自复审：opt-in关闭原行为不变；Receipt存在不跳过原Store hash冲突校验，但本波未独立验证samekey/differentbody；selected_writer_key仅供串行探针，不能拿这段可变闭包用于并发同key证明。完整b72方案尚有并发同key、samekey不同body、首次事件提交前失败、正式writer合同待下一波b73，不把本段称为完整合同通过。无UI变更，浏览器不适用。Goal active，权限不足不阻止这些安全工作。
