# AR1-b 第1/8步环境核验

2026-09-05，AR1-a提交b47b3c5a，authority AOS-000506。只做下一包预检，尚未登记AR1-b源码Task/Lease。

Docker desktop-linux引擎Linux29.6.1在线；SecurityOptions只有seccomp builtin和cgroupns，未报告userns/rootless。已有busybox本地镜像dc2d74b28e4c用于一次有界可信诊断：network none、read-only、UID/GID65534、cap-drop ALL、no-new-privileges、16PID、32MiB、0.25CPU、pull never、无挂载；读取/proc/self/uid_map后自动删除诊断容器。输出`0 0 4294967295`，未取得独立UID映射。

未发现colima/limactl/podman命令；Docker contexts仅default和desktop-linux。不能把本引擎在线认作231-2安全profile合格。没有启动领域包、没有变更共享daemon、没有停止任何现有服务。

建议补齐独立开发Linux VM/引擎并启用userns或rootless，独立于当前Docker服务；需明确允许新增本机虚拟化环境及其资源使用。不建议直接改共享Docker daemon或为了通过测试取消userns要求。环境选择明确后登记AR1-b Task并继续制品/IPC/监督器实现及真实隔离负向测试。此项是环境准入，不是业务开发完成，不能跳过标GREEN。
