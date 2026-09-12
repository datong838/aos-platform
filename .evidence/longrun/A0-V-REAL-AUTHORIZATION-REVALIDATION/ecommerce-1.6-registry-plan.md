# 新运行包 Registry successor 与宿主目录切换

2026-09-12，承接已批准的运行时重新首装方案。

输入固定为已提交 69819df7 的 build 与真实 qualification Receipt；三包 persistent session 的 exact/alive/released 必须全部存在。核对 build 输出树、Receipt 哈希、源码祖先及无相关路径变更；七项签名篡改反证必须通过。

从当前 1.5 successor 的签名根复制历史五坐标，再追加本次 domain 1.2、platform 1.2、growth 1.6；复用原持久签名密钥。历史 content hash 均保持，operations-base 不覆盖。新文件写入新目录，经签名策略复核后才可供 Registry 读取。

先备份隔离库，再用 RegistryService 逐包 create/validate/publish，重放逐项核对 exact version；中途失败可沿已有状态继续，禁止直接更新 Registry 表。安装记录数和隔离租户数量前后不变。

最后仅将 .env 的 AOS_BUNDLE_ROOT 从 exact 旧路径 CAS 到新路径；先保存仓外 0600 备份，以临时文件原子替换。trust-root 和 platform 配置保持原值。宿主下一次启动读取新目录；本步没有 Installation apply、能力调用或外部发布。

新增执行器：scripts/a0v_ecommerce_1_6_registry_successor.py；测试：services/aos-api/tests/extension_runtime/test_ecommerce_1_6_registry_successor.py。出口为首写与重放 Receipt、历史内容保持、正负租户计数一致，然后进入正式首装。
