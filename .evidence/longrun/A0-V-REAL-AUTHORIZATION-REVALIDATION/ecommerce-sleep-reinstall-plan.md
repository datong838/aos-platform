# 休眠失效后的独立重装与连续性

基线6fc85ce8。af1992e8已正式uninstalled@6，旧所有命令及Receipt保持。沿用已签名core/Niushop1.3.0、growth1.7.0及Host v12，不更换制品、不复活旧generation。

文件scripts/a0v_ecommerce_1_7_first_install.py增加与after-config-recovery互斥的after-sleep-recovery，使用独立state/ecommerce-1.7-sleep-recovered-first-install.json、a0v-ecommerce-1.7-sleep-recovered幂等前缀；必须核对af1992e8已卸载。scripts/a0v_ecommerce_1_7_configure.py同旗标读取新安装，拒绝旧e42/af，使用独立配置及configure/enable命令文件。scripts/a0v_ecommerce_continuity_observe.py对应只读目标，原两个入口保持。

验证文件tests/extension_runtime/test_a0v_recovered_configuration_target.py：旧默认及配置恢复不变、sleep恢复必须新有效UUID、双选择拒绝、state/key不交叉。之后正式create→apply→等待已提交→verify→等待active→四来源preflight/configure→enable；每个Operation只提交一次，已存在则只observe，unknown不换key。同一新实例跨deadline续租且3真实容器running，证据不能替代经营链验收。

已有控制身份仅复核，不扩展待批路由登记权限；四来源不新鲜则通过各正式Owner恢复当前证据，不延长旧观测时间。保留源数据/SSH缺口、八工作台及发布决定待办；m1串行、不push。
