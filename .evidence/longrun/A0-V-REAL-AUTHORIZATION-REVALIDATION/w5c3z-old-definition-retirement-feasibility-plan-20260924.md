# W5c3z 旧 DR 定义正式退休可行性方案（2026-09-24）

W5c3y `b8d86041` 已证实 12 个槽位全由旧 DR definition `446cc1ae-fa5b-406a-9446-d32104126dda` rev3 disabled 占用，新安装无 selection/control/definition。正式 Definition Owner 的 retire 要么当前安装控制权限，要么旧安装已正式 uninstalled 且 actor 为 admin；并要求 12 槽位无 running 或 executor 未停的 Run。本波只读判断，不调用 retire。

1. 核 W5c3x Resume 仍绿、旧 definition head/ref rev3 disabled、12 current member、12 schedule off、旧 DR 安装状态/etag/绑定/资源、actor 的租户 admin 权限。
2. 查询 12 槽位运行元数据：running/未证明 executor stopped、未完成 saved group/recovery、任何不确定提交边界；只查状态/ID/时间，不读 Run payload 或商城源。
3. 核当前 Definition Owner `transition('retire')` 的权限和状态契约，判断可直接正式 retire、须先正式卸载旧 DR，或须先清理未完成组；只输出下一波精确方案与停止条件。
4. verification 落盘、m1 commit；不修改旧定义、不动控制链、不手工 Run。
