# 说明
domain-admin-magic_change魔改版是根据https://github.com/mouday/domain-admin 的1.0.1版本基础上修改的。

- 页面


![image](https://user-images.githubusercontent.com/38614242/212626350-0ef13e9e-d3a9-4f40-83a2-d5103eb73cf0.png)
![image](https://user-images.githubusercontent.com/38614242/212628052-d0d4a1de-938a-4db1-81db-854037370fae.png)
![image](https://user-images.githubusercontent.com/38614242/212628251-3dc416ee-6032-4cb3-adbe-989debb88155.png)


- 邮件

![image](https://user-images.githubusercontent.com/38614242/212628088-72216213-2136-438f-9ed3-4f833e0c06b8.png)


- 企业微信


![image](https://user-images.githubusercontent.com/38614242/212628118-82169ba4-ef70-4df9-91c0-3459be0e3000.png)

- 导出导入文件格式


![image](https://user-images.githubusercontent.com/38614242/212629360-31c97a00-d039-4716-b9fe-85fb18e3538a.png)


# 功能新增与修改
## 修改
- 前端：修改刷新后返回当前页面
- 前端：修改了页面宽度
- 后端：修改了获取域名超时时间
- 后端：修改了获取域名时，失败了再尝试获取一次
- 前端：修改WebHook请求体提示
- 后端：修改WebHook的发送格式，默认空是使用企业微信机器格式
- 后端：修改了邮箱汇总格式
- 后端：修改了导出导入域名格式，并兼容以前的格式
- 后端：修改了一次性导入N条域名到sqlite
- 前端：修改底部展示条数

## 新增
- 前端：新增备注选项和展示
- 前端：新增证书过期时间展示
- 后端：新增备注字段
- 前端：新增刷新按钮
- 前端：新增删除所有域名和一次性删除失效域名
- 后端：添加上面的api接口

## 提示使用方法：
- 安装
```
pip3.7  install pip==22.3.1
pip3.7 install -r requirements/production.txt
```
- 启动
```
gunicorn --bind '127.0.0.1:8000' 'domain_admin.main:app' -D
```
- 上线
nginx转发到127.0.0.1:8000
