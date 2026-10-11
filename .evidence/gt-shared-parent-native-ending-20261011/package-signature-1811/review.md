# 精确包校验1811

binutils2.45.1-r1原包在固定SDK的apk verify下返回OK/exit0；末字节篡改副本exit1，原因file format is invalid or inconsistent。这证明当前格式损坏被拒绝，不能宣称完成了结构有效的伪造签名负门。原包SHA256见result.json，当前镜像公钥的独立来源仍未证明，也未将包与安装数据库C字段等同验证。

首次向只读rootfs复制失败，校验器未启动；r2复用原下载字节，只读bind输入、networknone、capdropALL、no-new-privileges，入口仅/sbin/apk。两容器已终态；各继承一空卷如实保留，未执行数据库或安装脚本。后续需要结构有效的签名负门与安装包标识匹配。无正式Root或执行授权。
