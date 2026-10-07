# 当前157原卷迁移与重启验收

本次事件：2026-10-07T17:15:17.220Z。施工线程唯一01a107a2-e9e4-7670-bc44-1144fa9b27e2；运行源码冻结于m1 5f0e4b50670450cd34c02a26709145ded5c76a10。

原权威容器9cc6091c…、命名卷aos-a0v-recovery-pg-data、数据库aos_current_preview_20260927保持同一身份，151→157六步原Alembic事务各自已提交并独立核实。旧602业务表在迁移后、服务启动后及浏览器验收后均保持数据摘要一致；新增私有表空。没有重发未知迁移。

首份一致备份完整603表恢复、独立原在线六步、独立Unix socket全恢复六步通过；精确停止原API/Web后，listen_addresses空、TCP拒绝、client0/prepared0形成零执行窗口，第二一致备份全库恢复及同冻结工具原Unix六步通过，才迁移原卷。全部备份与恢复卷保留。既有15 CHECK结合律文本差异逐项记录，其他目录/数据对比通过；不把文本原样相同伪称全部成立。

PG于2026-10-08 02:10:10 CST重新启动；API PID99269于02:10:12、Web PID99310于02:10:21。API从精确已提交冻结代码启动，使用既有签名安装Receipt，版本157、publishedVersions4、runtimeBindings0。首次浏览器目录500源于冻结部署遗漏bundles；从同一HEAD补齐1809清单文件且每个Git blob核对通过，原进程只读重读后恢复200。产品代码和工作树待交付模块均未更改。health/ready、Web代理两目录均200。

八真实工作台异步读取完成后逐页显示当前入口不可用，目录只读重读保持禁入；有效工作台安装0，技能已评测37、已发布0。可见组织org-org、工作区dev-project；dev-org两目录403。浏览器2/Tab1保留应用列表供查看。Host/worker/Provider保持off，本机预览重启GREEN，正式首链仍PENDING。

失败记录保留：旧SSH端口拒绝；离线镜像缺依赖/镜像导入对账；/proc socket挂载拒绝后使用公开overlay2 MergedDir只读socket；首清单archive顶层目录校验在提取前拒绝；151专用全快照助手对157新增私有schema拒绝（只读rollback），改用原public快照与旧602行摘要；Web /v1返回HTML改按已配置/api代理；无Bearer401，按既有本机dev身份重查。没有放宽安全门。

进行中的Goal实时回读仍为blocked，本线程没有写入blocked/paused/complete。受支持工具无恢复入口，操控Codex自身UI被安全策略拒绝，未改私有Goal存储；该能力缺口已报告。安全研发继续，不能宣称Goal已经恢复。

下一已登记安全项：联合物理容量合同中的Model报告消费门。已有原反例在report hash核验前失败并rollback，不能称签名负门通过；先核原解析器漏contract/subject/stage上下文的文件级方案与RED，再申请精确新代码scope；当前业务运行/Provider与未知结果重发继续关闭。
