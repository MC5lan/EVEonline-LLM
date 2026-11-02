# zh_guide_it_hosts

====== Hosts 加速 ======

===== 适用对象 =====

- 江苏人
- 网站上不去的人
- 觉得网站血妈慢的人

===== 操作步骤 =====

 - 下载 https://pan.lanzouo.com/b0742hkxe
 - 解压并打开其中的 ''CloudflareST.exe''
 - 复制结果中第一个 IP 地址 \\
 - 打开资源管理器，进入 ''C:\WINDOWS\system32\drivers\etc'' \\
 - 右键 ''hosts'' 文件，点击属性，去除 ''只读'' 前的勾，点击确定保存。\\
 - 右键用管理员权限打开 ''记事本''，拖入 ''hosts'' 文件
 - 复制下文，粘贴到文件最下方 \\ <code>?.?.?.? winterco.org?.?.?.? seat.winterco.org?.?.?.? forums.winterco.org?.?.?.? wiki.winterco.org?.?.?.? confluence.winterco.org?.?.?.? jira.winterco.org?.?.?.? bi.winterco.org?.?.?.? waitlist.winterco.org?.?.?.? sovtimers.winterco.org?.?.?.? wnt2.co?.?.?.? mrpig.link</code>
 - 将其中的 ''?.?.?.?'' 部分替换为第 3 步获得的 IP 地址
 - 保存并关闭
 - 如果发现还上不去，换一个 IP 填进去。不用的时候记得删掉。