## 环境
`python3.8`  

## 需安装依赖库
```Python
aiohttp == 3.6.2 
aiofiles == 0.5.0
```

## 使用方法
1. 编辑`config.ini`文件下的`[path]`变量，配置缓存路径`cache`，音乐文件生成路径`mp3`（用笔记本编辑就行）。路径示例：  `C:/Users/Administrator/AppData/Local/Netease/CloudMusic/Cache/Cache`
2. 运行`transform.py ` （命令提示符中输入命令 `python transfrom.py`） 

## 转换流程
1. 对缓存文件的数据和0xa3(163)进行异或(^)运算  
2. 用歌曲ID用网易云提供的API去获取歌曲信息  
3. 数据保存为`.mp3`文件  

****
### 2020-06-20 Grente
支持并发操作

****
### 2020-08-16 Grente
增加例子
如果安装异步网络模块麻烦，可参考[只需`requests`模块版本](https://blog.csdn.net/haha1fan/article/details/104464221)

****
### 2021-01-20 pl-mich
1. 增加控制台与本地文件的日志文件写入功能
1. 增加为输出文件自动写入标题、艺术家、唱片集、发布年份、歌曲序号、专辑封面等元数据信息的功能
1. 将原`config.py`中的设置信息统一至`.ini`文件来读写
1. 增加在查询歌曲信息失败时的容错操作
