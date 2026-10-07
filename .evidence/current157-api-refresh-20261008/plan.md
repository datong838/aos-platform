# 已验证报告修复后的API独立接续

本轮PG/最新基线API/Web重启验收已完成，不重复迁移或重启PG/Web。刚提交Release修复11b9dead，以git archive同HEAD完整services/aos-api、scripts、bundles生成新独立代码根（不导入待交付工作树）。先原签名Receipt/no-serve预检GREEN157，再核原API99269 exact argv/cwd/starttime；记录intent、SIGTERM、端口退出、启动新快照API、health/ready/版本/只读目录/过程identity。原602表摘要与public快照须保持本次维护最终值，Provider/Host/worker off、签名源/租户/安装禁入不变。仅Task API维护scope，零DDL/无生产执行。原进程/未知结果禁止重发；原日志与两代码快照保留。

新增本目录refresh-api.py，唯一claim避免重启重放；执行前当前HEAD/authority/Task/Lease/sourcePG ID与157一次只读对账，预检失败不停止旧API。API改为当前已提交HEAD，不接受工作树override。最后实际浏览器只读目录复验，完整业务与长期Goal不完成。
