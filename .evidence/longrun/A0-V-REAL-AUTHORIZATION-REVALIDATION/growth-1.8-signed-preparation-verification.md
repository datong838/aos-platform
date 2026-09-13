# UQ5-B3d 永久签名准备

2026-09-13，基线8f533681，m1不push。

实际GROWTH_UI_1_8_SIGNED_PREPARATION_GREEN，新根14版本，growth1.8 contentHash sha256:ac3b80551ca9325b69853d10f41d61134fe4c0a3f8ebcf83c0343deb0147bd5f。旧13版本共577文件在新根逐字节相同，重复准备回执完全相同。构建/资格回执、当前source、签名与信任根已复核；无密钥内容输出。

代码测试11 passed，覆盖私有profile、1/2/24及2048心跳、释放、精确readProbe hash/类型、原签名追加/幂等/CAS回归。Registry发布/安装/环境修改均0。

真实发布边界：RegistryService强制发布人与创建、验证人分离。旧helper不同actor名称和固定roles不能证明当前真实主体职责，新的CLI仅签名准备，不调用该publish/switch_root。当前正租户成员仍runtime-owner(admin)、user:dev(owner)，原独立审批身份待核验，不造审批主体。签名准备不等于Registry已发布或真实安装。

下一波继续UQ6：针对031~035只新增读取账本/角色/固定函数的备份恢复演练与主库升级准备；旧Host和业务路由保持既有状态。发布/安装待真实身份和产品授权核验，其他工作不中断。
