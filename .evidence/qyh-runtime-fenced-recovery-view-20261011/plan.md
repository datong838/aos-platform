# 栖月汇终态禁入恢复提示修复

依据231-3当前状态投影、资源释放后只读对账、未认证不得开放控制动作要求。全恢复主Task不收口。本Task仅修复真实恢复安装407059df的诊断误导：enable历史succeeded，binding desired=enabled/enabled=false/fenced=true/observed=unknown，3资源全部释放、租约过期；现行视图却持续显示正在禁入或排空。

文件：services/aos-api/aos_api/extension_runtime/runtime_view.py；services/aos-api/tests/extension_runtime/test_runtime_resource_health.py。在原get_installation已完成运行状态推导和原资源存活读取后，仅当effectiveState=fenced、operation确为终态、资源非live时，改为needs_attention、allowedActions=()、明确恢复对账原因。不改绑定、不授disable/enable、不创建UI会话、不推断未知外部效果。active operation、可合法configure/enable的disabled、ready资源丢失时既有安全disable动作不受影响。

RED覆盖终态成功/失败/取消与资源缺失，反证active operation、不明operation、仍live资源保持原状态。GREEN专项+安装API/界面/目录相邻；实际库原解码审计证明状态输入来自真实安装。只读产品评审核零动作/不误称排空；不以单测证明全系统八页恢复。回滚仅撤销该投影条件，不变更数据库。旧22个tracked改动保留。
