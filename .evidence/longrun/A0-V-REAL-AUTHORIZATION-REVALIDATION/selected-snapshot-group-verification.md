# 当前配置绑定组读取验证


SC4-5f4c：当前配置绑定组读取完成。新增pipeline_selected_snapshot_group.py，当前sourceConfigurationRef/direct状态严格核验，私有连接一次整组读取，原成员最严格界限不可放宽。52项测试通过（3.86秒），AR2 ar2-7扫描1913模块、五类错误为空，memory revision AOS-000573 GREEN。测试中的权限/连接均明确替身；本波无真实源调用，无主库迁移/对象写入/Fulfillment。下一项：组认领提交确认后，真实原输入与manifest原子保存、精确重放与未知结果禁止重读。

红阶段：缺失模块导致ModuleNotFoundError。绿阶段：新增12项，连同旧单表/组读取/组控制共52项。旧单表文件未修改。租户/窗口/版本/状态/组限制失败均source calls=0；源错误/总时限/未来结果拒绝均调用1次并关闭。仅可信Host在当前组Owner内调用；此数据结构不构成执行授权。
