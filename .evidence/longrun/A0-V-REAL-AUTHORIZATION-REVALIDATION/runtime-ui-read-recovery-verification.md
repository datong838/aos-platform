# UQ3-B 到期投递恢复验证

2026-09-13，基线20231663。新增expire_ui_read_deliveries，固定scope、1..100限额、请求锁SKIP LOCKED。未领取到期请求直接expired；已领取请求仅在关联Attempt已终态后expired，仍running者跳过且不占分页名额。保留原claim，无新Attempt或重新入队。

14 passed、7项既有warning：4项新增恢复+10项领取封存回归，真实隔离PG验证到期前不变、分页/幂等、现有abandon_expired_reads先收束Attempt后队列终结、running不阻塞其他到期项、负租户和非法限额。AR2扫描1844模块、163分类、93迁移，错误集合为空。结果仍是存储协议验证，不是业务调用验收。

未改主库或运行宿主。下一波UQ3-C补运行角色的当前身份锁/请求有限列更新权限，再将快照、签名模块及原PreparedJob接入具体消费者和RuntimeHost。API专用角色保持无直接表访问。自然业务链仍未完成。
