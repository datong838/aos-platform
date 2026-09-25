# W5c9f｜恶意自洽输入夹具验证收口

1. 复习 231、W5c8q/r、W5c7t 与当前全机 closure no-authority。
2. 方案 `m1@36e6ead6` 先提交，夹具文件清单 `m1@3bbae34e` 在测试前补充。
3. `a0v_045/097/098` 静态约束审计；只使用一次性 PG 合成数据。
4. 新隔离夹具复制 fixture ingress 的准确 envelopeHash，提交格式/哈希合法但错误 rowsHash/rowCount 的独立 immutable group/input；**没有**调用 witness writer。
5. 首轮 ordinal=700 触发源 claim CHECK，修成合法 2 后专项 1 passed、7 warning；测试库/临时角色残留 0。
6. 复审：canonical/manifest hash 自洽不等于行级真实性；sidecar=0，不能宣称 writer 或 ACK/closure 通过。
7. 8080 业务浏览器离线，18181 `/docs` 不替代真实验收。
8. audit/verification/test 精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9g：先方案，在隔离 PG 用精确 operator/身份测试 `a0v_098` 对此夹具的实际处理，分离“保存原字节”与“语义授权”；不迁真库、不发 ACK。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。
