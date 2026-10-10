# Task10 完整准备链写入合同与安装差异

Rules：231八步、joint §11.3、产品v3、m1单写，AOS-001688，HEAD8f143817e。当前Task10 receipt/owner/Lease一致、27 Lease无重叠，原件库READONLY。前波22已知事件只是子集；源码已有Judge Intent/Target call/Target ledger完整准备工件，但原R22目录缺四表，不能从子链直接得full finalizer。

候选①完整原生准备矩阵：比较原source-generated工件与当前安装，补齐后续writer/event；②正式Root/WAL/Source信任收口，依赖正式范围/外部裁决。本轮①，先调查RED确定完整原生验收缺项，而非跳过四表。文件仅本Task E：本计划、read-full-writer-installation-r1-1688.py、full-writer-installation-r1-1688.json、复审及后继精确原生计划。产品文件只读，不修改已Delivery组件或原deny。

原Python *_statements生成函数纯读取（不执行SQL），提取每一CREATE FUNCTION的实际完整signature/bodyhash并与真实pg_proc原定义比对；只原R22连接READONLY，明确5441/cluster。逐helper手读直接SQLwrites及调用关系，不能regex猜动态SQL成为授权；正则仅用于提取明确静态CREATE函数原件、failclosed遇未知。缺函数/表、body漂移分别登记，不能新GRANT修好旧实验或修改真库。后继完整矩阵必须独立fresh保留库、单native writer、新批准/Root/签名原件、完整Target/Judge Intent/call/ledger同caller和全部deny真实COMMIT负门；当前不执行未知效果。

边界：生成器与hash不证明正式Owner/ACL/Root安装；Judge awaiting_target_result不是已完成Judge/Usage；Target initial prepared_only/counts_as_inflight=false不是经营执行。scope仍完整joint主线，不产生全TaskDelivery；正式HostworkerProvider关闭。
