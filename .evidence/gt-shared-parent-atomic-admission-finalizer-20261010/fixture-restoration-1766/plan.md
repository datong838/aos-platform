# 隔离夹具完整 catalog 恢复
Rules：231、完整联合准入、m1 单写，原 Main evidence scope；本步仅隔离库 admin 可回滚事务。产品/正式库/其他分支不改。
具体文件：catalog_fixture_restore.py、native-restoration-test.py、result.json。helper 只生成原 epoch 夹具恢复语句，加上原源码 FACT 定义，不执行、不授权、不延长时限，不接受调用者任意SQL/body。新的完整调用夹具将在原 physical finally 的原 legacy 恢复位置调用本 helper；旧尝试和旧生成器不修改、不重放。
RED：完整固定新家族安装并确权；只执行旧 legacy 恢复，识别器仍看到新 FACT，必须拒绝混合身份。GREEN：helper 再恢复原 FACT 后识别器返回False；原 private INSTALLATION 由原 publication Owner 实际执行通过。最后真实 rollback 与新连接精确核对所有相关函数/Owner/ACL。helper-only 不给 Delivery，不等于新完整 Receipt 验收。
