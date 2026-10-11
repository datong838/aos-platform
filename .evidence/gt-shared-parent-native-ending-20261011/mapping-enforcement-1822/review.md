# 进程内映射约束可行性1822

固定SDK静态helper，scratch/no mounts/UID501/read-only/networknone/capdropALL/no-new-privileges，仅helper安装AArch64 seccomp规则；不改PG、Docker全局策略或正式服务。mprotect PROT_EXEC被EPERM拒绝；直接mmap系统调用PROT_EXEC被EPERM拒绝；普通RW分配、写入、读取、释放通过。

r1进程明确exit8，原因是原断言要求libc mmap errno=EPERM。r2保留过滤规则，增加libc和直接syscall诊断，实测libc失败errno12、直接syscall失败errno1；修正断言同时要求wrapper失败和raw EPERM，exit0。原失败和源码保留.r1。没有以放宽安全限制修复。仅观测错误码差异，不凭该实验推断库内部源码原因。

方案一致。过滤器只检mmap/mprotect两个入口，并非完整安全策略：其他syscall、已有可写执行内存、proc mem/ptrace、多线程、动态加载与完整PG功能兼容均未验证。不能部署本原型或据此授予native arm。下一必须先列出完整写入/映射途径和允许验证器需求，再决定可实施的进程生命周期合同；完整Root/COMMIT仍待证。
