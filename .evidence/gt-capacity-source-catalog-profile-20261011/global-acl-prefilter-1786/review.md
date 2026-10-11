# 全目录NULL预筛一致性复核

仅两条全目录列ACL扫描增加x.attacl非NULL过滤，原权限类型、转授权、允许锁列与数量条件逐字保留；不限制schema或relkind。PG实际aclexplode为STRICT/STABLE，NULL返回0行；首只读检查误断言IMMUTABLE已纠正并记入equivalence-review，不依赖不可变性作证明。旧生成器字节相同，原发布SQL未修改。

跨schema临时表实际owner列授权/grant option/撤销与PUBLIC分支等价，完整身份/混合/ACL负门及Main相邻54PASS；原生事务回滚和独立回读在测试内执行。无页面改动。

同查询结果5项，old8.7–9.4ms/new1.6–1.8ms。全Source新鲜试验可比阶段调用次数相同，多个阶段12–13s到10–11s；本轮v2Receipt/最终物理比较返回且代码进入collector前的断言通过，但正例payload写入在collector之后，因此没有完整receipt正例文件。collector在17.545s触发Source过期，整体仍RED，后续迟写/COMMIT负门本次未到达。不可声明完整Task/首链通过。

独立回读同cluster、九表全0、其他会话0、产品hash相同，统计库设置恢复none，正式库未动。下一候选仍原FACT剩余catalog扫描与完整Source期限成本；须继续保留全部当前性检查和原期限，禁止盲目重试/去检查/缓存。
