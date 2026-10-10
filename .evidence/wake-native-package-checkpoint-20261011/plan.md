# 原生包检查点接续修复
Rules：231、机制01/07/08、先方案后代码、m1单写、真库只读；不恢复旧CLI调度器、不改Goal、不授工作或业务权限。
已登记候选1：观察器原生包识别缺口修复（本项，机制落地已授权，无外部依赖）；候选2：原完整NativeEnding模块映射来源/回调与RI固定点（原Task授权，依赖精确安装和完整Main末门，不因本项通过而通过）。先修复会阻断当前精确检查点观察的机制缺口。
精确代码文件：scripts/long-task-watchdog/aos_wake_progress.py 与 test_aos_wake_progress.py；本Task .evidence/wake-native-package-checkpoint-20261011。NativeEnding原Task负责其checkpoint.json与引用清单，不扩大新Lease范围。
现有通用后缀保持；额外仅 services/aos-api/postgres-extensions 下 .c/.h/.control 与名字恰好Makefile；不得把所有无后缀或所有控制/二进制/JSON视为代码。Git代码年龄检索与checkpoint一致，避免C-only提交不进入代码年龄。路径大小/隐藏/敏感/符号链接/精确Owner/当前Authority/原Task基线/活跃Task==Lease/32文件限制保持。
原生检查点直接跨Task证据非法；建立本Task精确path+SHA引用记录，保留原引用不删证据，不宣称观察器递归核验依赖或已授权限。实测前独立复核引用hash。
RED：新包四种文件能读取，C变更fingerprint变化、记录字节不变；C-only git提交被观察，随后文档提交不更新代码年龄；越界包/二进制/假Makefile/控制文件/Owner/symlink仍拒绝。实现后专项+整个long-task-watchdog累计，原实际native checkpoint只读两次/CLI原heartbeat事件一次，无数据库或旧Run重放。
收口：复审、verification、独立回读、精确m1提交、机制Task Delivery（仅该合同）、Authority CAS与AOS/Prime同步；原NativeEnding与整体Goal保持ACTIVE。Browser不适用。
