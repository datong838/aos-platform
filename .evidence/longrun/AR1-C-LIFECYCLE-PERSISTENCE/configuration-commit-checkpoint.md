# AR1-c 配置指针原子提交检查点

2026-09-06；基线0fd7fb9b/AOS-000534；代码由主生命周期Lease覆盖。

配置提交从不可变accepted重建exact安装/代次/configRef，在Installation→operation→binding锁下检查当前ETag、操作CAS/deadline、fencing事件及hash、绑定accepted revision+1、disabled/fenced/draining。按原actor重读当前配置/引用权限，受信drain reader必须覆盖该代全部历史epoch已准入和未决工作；fence_epoch仅水位。成功切换精确config_ref、binding revision+1，保留epoch，保持disabled/fenced且observed=unknown；事件/outbox/succeeded原子提交，不声称ready或热改运行会话。

初次13项缺模块Red→13passed9.64s。独立Prime指出排空期间引用到期窗口，补真实DB时间跨期（operation未到期）反证；同时补伪fence revision无事件反证，2Red后修复：最终succeeded前再次当前配置/actor校验及fence不可变事件核验。15passed10.23s；另旧epoch未决与canary测试合计17项，最终累计657passed/6既有warnings/97.64s/exit0。独立Prime最终复审无新增实质问题，未替代测试。既有JDBC退出日志关闭流警告不改变exit0。

未部署共享表、未接真实异步broker drain reader、无真实业务写/Provider/费用/页面变更，因此不声称业务排空或页面验收完成。AR1-c仍IN_PROGRESS、新增业务场景0。下一段合并推进配置命令接纳、启用前目标/健康验证及停用，继续专项迭代后联合验收，不把单个内部原语当业务闭环。
