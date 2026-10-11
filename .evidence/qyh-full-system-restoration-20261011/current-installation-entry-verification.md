# 当前安装只读入口核验

本波遵循原全系统恢复方案，新增真实安装读取而不是诊断候选的PUBLISHED投影。修改scripts/a0v_qyh_restored_http.py及专项test_qyh_restored_http.py；仍没有serve/数据库写命令。

RED为12个新增选择案例缺少实现，原9个库存/租户/schema门通过。GREEN专项21通过；相邻含原preview和current_installation_release_evidence共34通过/9 PostgreSQL依赖测试跳过。日志current-installation-entry-red.log、-green.log、-adjacent.log。9项跳过不计通过，真实库读取另行记录。

真实有限LOGIN+READ ONLY审计三个保留安装叶：407059df与89975129由原发布/锁/签名读取器取得历史有效证据，但当前精确四包门拒绝（Core1.4.2/Growth1.10.2）；ef5bc0c3仍Core1.4.0/Growth1.10.0，所选较新保留签名目录不包含该旧四版本，原读取器拒绝release evidence。三个安装current/active revision均5。见current-installation-entry-live-audit.json及current-installation-exact-lock-coordinates.json。没有自动继承active/权限，没有重放旧12Run，没有修改原安装。

架构一致性：原runtime-image current reader要求live resource lease，不能让API的无Host预备核验反过来先开启Host。本入口只复用read_current_installation_release_evidence：原租户RLS、安装状态、lockhash、真实Registry status/currentness、不可变签名及bytes校验全部保留，再限定选定四坐标。配置、Owner/身份、业务权限和Host/worker仍分别验收，报告显式不授start。

最小复审：旧库存默认CLI行为/旧preview固定数据库门未改；新三个CLI参数必须一起提供；有限身份私密文件的旧目标和权限门复用。原源码、业务数据和既有修改均保留。当前版本组合已完成离线镜像/schema诊断，但两新Registry版本仍validated，三个历史安装均不满足当前四包门，八页面未恢复，整Task/Goal继续ACTIVE。
