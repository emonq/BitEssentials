# BitEssentials

[![docker-builder](https://github.com/emonq/BitEssentials/actions/workflows/docker-builder.yml/badge.svg)](https://github.com/emonq/BitEssentials/actions/workflows/docker-builder.yml)

一个帮助北理工人更方便地获取教学内容的工具（集）

# 功能

- [x] 保存用户会话到数据库
- [x] 乐学课程文件下载
- [x] 导出课程表为ics格式
- [x] 导出考试安排为ics格式
- [x] 自动查询成绩并推送
- [x] 均分计算
- [ ] 日历托管和自动更新

# Telegram机器人部署方法

- 安装依赖`pip install -r requirements.txt`
- 复制配置文件模板 `cp config_sample.json config.json` 后填写`config.json`
- 后台运行`nohup python main.py > bitessentials.log &`

## Docker部署

- 下载 [docker-compose.yml](https://raw.githubusercontent.com/emonq/BitEssentials/main/docker-compose.yml) 
 ```
 wget https://raw.githubusercontent.com/emonq/BitEssentials/main/docker-compose.yml
 ```
 
- 下载配置文件模板

   ```
   wget https://raw.githubusercontent.com/emonq/BitEssentials/main/config_sample.json -O config.json
   ```

- 修改配置文件 `config.json` 的内容

- 启动

   ```
   docker-compose up -d
   ```

   
