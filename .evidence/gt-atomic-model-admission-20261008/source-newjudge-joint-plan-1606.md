# 真实 Source + 新 Judge 同 caller 试验

基线a1a814a45f5840cef235ca3b57bcea08f5f5b5f8/AOS-001606。候选①新Judge共享debit真实Source正向及cap/replay；候选②完整newJudge Intent/input/finalizer协议。本轮先补①缺失证据，不能继续凭安装拒绝门宣称分配完成。

资源调查：原a0v VM仅约900MiB可用，旧5435三个库分别有原注册记录/Source，不能重放zero-state fixture；早先缺C失败库也有immutable deployment/registry1，不删除或改写。另一已运行aos-extension VM 3GiB，有2232536KiB可用、14GiB disk/1116488freeinodes，满足768MiB新实验容器+256MiB reserve。无需扩容、启动/停止VM、触碰当前PG/API/Web。新5436/native独立cluster、新named test-only volume、原精确image sha256:a0eb61b312f90f7c5891afc088edc2824ae8eae1dd21ab8ba0e3ef78b1027eb8（已含原C）、768MiB内存上限/noSwap、max_connections30/shared_buffers16MB。仅导出/导入该已缓存image，禁止下载/删除旧image/卷/库。新秘密文件0700/0600在专用目录，证据不含秘密。

文件范围：本Task修改services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py，原JudgeTask修改services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py，原Source/property代码不改；lab建立独立Task精确资源与证据Scope。修改前核所有Lease和强投影。只追加可选fixture参数/新测试区段，默认旧流程不变。

在真正新数据库完整迁移159、template1原C signature正负验证通过后，运行原实际签名Source/SCRAM physical fixture；Source Provider作为原Judge/Target合法Model应用的同Provider来源，另发真实signed Rule+新Suite/独立newJudge批准。首个wholeparent trial采用实际occupation SCRAM连接，原Source/accountguard先于Model Registry/fees/buckets，原Store创建新Target/newJudge parent后，实际新Judge窄fact回读、sharedJudge debit1case10minor/replay/异UUID同case拒绝/第二case超parentcap拒绝/未finalize SET CONSTRAINTS拒绝，在强制rollback保存点内完成；完整caller最终rollback，独立xid/rows/catalog/Source签名/角色撤权核对。

全case Manifest绑定真实Source/account refs，但完整4腿allocation/Intent仍未形成。本步验收真实Source+新用途原parent在同原SCRAM/xid native准入事实与shareddebit路径，不声明4腿联合COMMIT/transport/Usage/业务首链。新阶段通过后必须继续完整input/Intent/finalizer设计和实现；五父Task保持ACTIVE。

每次attempt写当前HEAD/authority+新fixture随机ID，未知结果先只读对账；不重发外部效果。容器/库/卷保留，不自动清理。原容器ID/启动时间/端口/mount baseline事后比对。容器故障只限制本动作，继续其他安全项，不blocked。

镜像失败只读对账：源containerd使用OCI manifest a0eb61…作为ID；目标经典Docker使用同manifest引用的config 1a7265…作为ID。保存归档hash不变，逐项验证manifest/config SHA及原完整diff_ids、Config和架构一致后，只接续尚未执行的凭证/新volume/container阶段；不再次load，不下载，不更换文件层。来源与运行ID分别登记。

目标VM未挂载宿主私密目录，main run125明确未创建main容器；已创建新volume和init容器exit0保留。改为仅create新main→docker cp原0600文件→start同ID，密码仍不进入环境/参数/日志，不改VM挂载或共享目录。

R1 RED：新库完整159后Source成功发布，但试验提前编译依赖原Judge request %ROWTYPE的函数，原Judge Store尚未初始化其表，UndefinedTable/事务rollback，finally关闭角色；非产品授权门失败。将试验函数安装移至原Judge Store已完成初始化、Source account prefix之前；R1库Source保留，仅另新数据库运行R2原fixture，不重放旧Source。

R2 RED：旧Source窄consumer要求原Bearer consumption packet，试验误传Source原JSON被CAPACITY_OCCUPATION_PROTOCOL_REQUIRED拒绝。改为原_consump­tion_packet(command)（真实JWT由原fixture签发），不伪造Source、不放宽原consumer。R2保留，另新库R3；finally恢复角色/原函数。
