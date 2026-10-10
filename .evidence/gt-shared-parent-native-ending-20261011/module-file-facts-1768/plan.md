# 完整 native ending 的模块字节闭合前提
Rules：231、原联合3/11.3、原NativeEnding Task Lease、m1单写，真库只读。上一波实际八节点Receipt/物理/迟写/缺门COMMIT有证据，正向ending仍未通过。
两个已登记候选：完整末门模块/回调闭合（本项）；原Main最终Source/当前时钟及实际COMMIT（依赖完整末门）。选择前项的必需原生字节事实，不把它当整体末门或较窄替代目标。
精确产品文件：services/aos-api/postgres-extensions/aos_admission_end/aos_admission_end.c 与 aos_admission_end--0.1.sql；测试services/aos-api/tests/aip/test_shared_parent_native_ending_pg.py。Makefile/control及原pending/paths APIs不改。
新增零参数Owner-only loaded_module_file_facts()返回jsonb。取原加载器快照路径，不接收调用者path/allowlist/Hash/权限。磁盘常规文件逐个SHA256及descriptor前后stat/路径身份复核；vDSO明确virtual且无文件hash。两次模块快照必须相同。文件大小限定256MiB/每件、循环可响应取消；异常关闭文件与hash资源。
仅当前磁盘文件观察，不能声称已证明映射页、源码构建来源、正式不可变安装、所有callback行为或最新注册最后执行。可信包来源/当前Root/写者闭合/事件RI固定点/最后决策时钟/实际COMMIT仍需下一完整协议。无arm/API授权/表写/trigger drain/全局配置改变。
先添加新API原生RED；新临时唯一二进制编译，不覆盖已加载/已安装原件。新SQL尾仅原owned fixture事务内安装后rollback，核原pending元数据精确不变。专项：Owner/ACL/零参数/正文符号、磁盘SHA与独立工具一致、虚拟模块标签、独立临时外来模块变更可见；相邻复验旧module4项/pending队列。Browser不适用。
