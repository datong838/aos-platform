# 安装包分析启动命令验证

基线1336a602。固定analysis_advance/build_analysis_start复用既有AnalysisRuntimeRequest和canonical_command_hash，纯计算无Host写入。

Red：原handle拒绝9用例。首次实现后测试延迟import遭SDK路径移除，修正测试载入顺序；清册新增模块分类与requiredPaths，无修改历史preHash。Green：新命令/注册/恢复分析协议共35通过。AR2-7 1884扫描169分类93迁移，错误数组均空。

正例经现有Host严格START解析，重复一致且输入不变；未知字段、错误用途/引用类型、receipt混入、无时区/小数秒、空白key均拒绝。测试为源码，不是当前已安装候选。历史候选不改，未部署/未创建Run/未push。

下一波：Installed分析命令port，实际当前安装调用前后复核，严查返回命令与输入exact绑定；再接事件claim/当前方案/Host事务承接。
