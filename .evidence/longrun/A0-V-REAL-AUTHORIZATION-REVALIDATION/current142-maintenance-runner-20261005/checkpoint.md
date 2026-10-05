# 维护执行器施工检查点

Task w5cb4-current142-maintenance-runner-20261005 ACTIVE，不是完整Delivery。正式plan Task亦ACTIVE。已实现来源精确门（包括原合法只读backup挂载）、O_EXCL+文件/目录fsync未知attempt拒重发、窗口TCP实际终止码/旧client/prepared拒绝。首次模块缺失RED，进一步unknown TCP观察None/-9/bool误放行真实3failed/11passed RED后修复type int positive；maintenance14+restore17累计31passed/0.20s。没有当前变更入口、没有服务停止/原库DDL、没有完整维护sequencer；不能用31测试宣称维护runner完成或正式迁移通过。

下一在同文件完成精确进程指纹/私有恢复配置、正式Task/Lease与Authority校验、原socket命令及逐阶段journal、隔离完整 sequencer验收，再独立source维护Task。记录当前真实Cmd/无restart/已核实两个leaf启动路径；仍须固定恢复器窗口并测试未知调和与迁移后恢复失败处理。原共享上下文保持此前真实135事实，没有新增模型或业务执行。

09:54更新：完整固定顺序journal/isolated runner已实现；越序/失败不进入restore/重复attempt真实RED2failed后修，最终累计33passed/0.23s。完整实际isolated sequence两次terminal0，最终16.123s state .aos-maintenance142-77b39l3h：源新容器恢复原135精确592表/TCP baseline→关TCP重启+排空→socket停写全备→第二新容器完整恢复精确→原Alembic七步到142/逐步回读→旧行/原权限及精确Source增量/新空表/三NOLOGIN角色无成员高权→恢复TCP重启→TCP/schema142回读。两新目标/卷和全journal/备份保留。生产mutation entrypoint仍无；source服务停止/恢复、独立资源Task/Lease校验、正式窗口与浏览器未完成，完整Task保持ACTIVE，不以isolated runner交付代替真正current迁移。

进程切面实际补正：源API67821无child、Web67820有esbuild67827，原leaf假设被真实guard拒绝；方案已改为API leaf/Web精确helper合同，unknown children/argv/PPID/UID/启动时间/cwd/listener漂移仍拒绝，无kill入口。最终累计43passed/0.24s，两原服务原plist完整argv/cwd/loopback独占listener与指纹实际只读通过，signals0。新Popen拥有的Vite PID4681临时端口59939正常terminate/wait0，helper4684实际missing且非zombie，child signals0；原18434占用前检拒绝无操作。此实验只证明拥有的新实例退出行为，不证明现存WorkBuddy进程原子接管/安全停机；现有runner Task保持ACTIVE，当前原库135/服务未动。下一正式控制需确定现存进程支持通道、停止前最后fingerprint复核与恢复器禁入；不把ps快照当原子进程句柄。
