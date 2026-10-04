# b73 License事务合同候选

代码e942169a、docs db48349b、权威AOS-001329；上位231/BIND-1和b70–b72框架保持不变，本波补全既登记的b73隔离探针，不生产化。

仅两原extension_runtime测试文件。opt-in B73_TRANSACTION_PROBE必须配b72/b71/b70；独立B73_RECEIPT_GUARD控制候选，先guard关闭保留RED。生成全新bundle（有效ExactRevisionRef与marking），在原随机epoch表插新exact行；原Store真实revoke。每次请求使用独立闭包捕获不可变key/body，不共用串行key变量。

先全新事件的提交前强制异常：代理commit在实际commit前抛错，原事务已插epoch/event/Receipt但未提交；退出回滚后独立admin证epoch0/event0/Receipt0。然后blocker持epoch FOR UPDATE，两个同key同body真实writer精确PID都等待blocker（8s/10s有限），释放后两者成功且epoch1/event1/Receipt1。guard关闭应真实RED(epoch2)；guard开启先锁exact epoch再查tenant/operation/key Receipt，无Receipt才推进；原Store仍负责canonical hash与冲突。最后samekey不同body须原IdempotencyConflict，状态不变。

相邻b72两个顺序、default专项；编译/diff与方案自洽审查；测试库前后计数和测试异常自行清理。正式writer数据库强制门、scope canary、初始化来源/Owner/install epoch、多来源锁序、迁移恢复须后续独立合同，不借本波放行当前库。无页面改变浏览器不适用。Task/Delivery精确提交及01/06/接续/D-wave对账；不push、不动其他分支及用户改动。

首跑直接父PID假设过强，实际等待链可能经过另一个writer的tuple lock；只读pg_blocking_pids精确PID图必须两条都最终到已知blocker，接受间接锁链，不延长等待，不将首跑定位为业务RED。
