# UQ6-A 读取账本真实主库部署

2026-09-13，执行器提交e3d49c2d，m1租约A0V-UI-READ-LOCAL-DEPLOYMENT-20260913-V2，不push。

实际prepare通过：aos_meta_head@a0v_030备份5310752 bytes，0600，完整恢复到拒绝PUBLIC CONNECT的aos_ui_read_20260913_test，再精确迁移031~035。19张关键业务表迁移前后指纹相同；队列0，FORCE RLS，runtime仅SELECT/11状态列UPDATE，API无直接表权限，5固定函数精确角色且PUBLIC拒绝。

实际apply与独立readback均UI_READ_LOCAL_SCHEMA_DEPLOYED：主库a0v_035，19张表仍与备份前相同，队列0、权限核验通过。执行意图和证明保留且fsync，未重跑apply。仅增量DDL/角色/函数，businessWrites=0。

原RuntimeHost PID6606仍运行，原3业务容器和2PG容器保持；API旧部署继续运行，尚未重启原Host或切换签名安装。旧/新API独立登录身份与原宿主升级、永久包实际发布安装、浏览器/CSP/真实经营读取仍未完成。Registry职责分离需要真实身份，不凭已有签名准备绕过。

下一波：置备并用真实非超级NOINHERIT登录验证专用UI读API连接（仅aos_ui_read_api可达、0600文件），复核正租户原主体/负租户/他人/直接表拒绝，先副本后主库；然后受控API装配。大目标的自然首链、八场景、连续观察与发布决定仍待真实执行。
