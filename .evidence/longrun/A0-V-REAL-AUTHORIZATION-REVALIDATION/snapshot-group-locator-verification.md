### SC4-5i6 原运行快照组定位验证

PipelineSnapshotGroupLocator复用原member唯一键联查claim/input，要求runtime租户事务；精确验证原binding/requestHash、manifestHash、run成员顺序和cutoff，返回原group/actor/control-run bindings。缺原input/未知run返回None，不按时间猜组、不读source、不赋予当前执行或Readiness权限。

隔离PG10项覆盖：逐成员定位同组、准备前None、未知run不替换、差1微秒拒绝、错tenant/非法输入拒绝、原唯一约束、原binding/manifest损坏拒绝。首次测试误按调用顺序比较，修正为原Owner的control resource_id排序；后一次9过1夹具失败，原FK正确禁止修改已引用requestHash，改为测试专用破坏binding body而保留原FK。最终损坏反例2项5.11秒通过，其余9项在前组合通过；未放宽产品约束。AR2扫描1928/187/93五类错误为空。主库/数据未变。

下一波SC4-5i7：给原GroupClaim/Input/Assessment/Quality增设独立completed-current只读入口，复用原单run read_completed_current和ControlledIngressJournal(completed_read=True)，要求组内全部成功/执行器已停/原Dataset Receipt与完整投影记录合格；默认running写路径不变。定位到组后仍需此当前只读守卫。暂不支持换控制代次的组续期，不把完成态历史变成新写许可。
