# Niushop1.5维护替换实际启用

2026-09-13，m1，Host v16 PID21028，加载代码2b2ab503及1.5完整签名根。旧Host已退出，无双Host。

新安装eda57424-b8cb-401e-a6f7-94220cb4f9ef，composition9244d05e-0ec6-424f-a73a-a82e5cec7d97@1，lock sha256:26e8189ca75d124fe49b27c5e6922a5115071e8f2a7e126c904e3949e4539f59；新generation23afd05b-762c-406a-adfb-247a14412b9f。prepare 2c1e04e4-a917-4a1c-9dce-61fc22c8c102 succeeded，verify 7a731a57-7a99-4edc-9edd-65ec7772e58a succeeded，安装active@5。三个真实签名资源创建，未进行业务调用。

私有配置入口a0v_niushop_1_5_configure.py仅替换新根和exact新目标，原入口默认不变。四源当前授权检查通过，配置f134da1e-69bf-4406-917a-c0e665e12e02@1，hash sha256:af72d785cb326f4ac28b0f768402c2b7f6beaf0507f14490640b3713ccba8adf。configure 96bdc8a4-f218-4fec-8946-58fbce7971fa succeeded；enable 8e1af8d1-523c-4207-a6b7-dbb341e555c7 succeeded。当前新binding@4/epoch3 enabled=true、fenced=false、ready。旧binding@7/epoch5 disabled/unknown、fenced=true，旧安装active历史保留。单写保护已实际经过enable提交。

配置profile首次4 failed（文件缺失），实现4 passed；补充未知结果防重发/只读preflight不写intent，与命令测试合计34 passed。所有mutation先exclusive intent，未知结果只观察。stage/configure/enable实际回执和独立observe均已保存。

此时API仍PID12426旧代码，尚未重启；Product真实行未读取、goods_content NULL兼容仍待实证，P03/SKU/关系未完成，自然Case/Run与八工作台业务场景未完成。旧P01数据和Receipt、源连接配置未改。未push、未外部发布，230L0挂起。下一波重启受控API，真实P02源选择/契约/控制授权及首读。
