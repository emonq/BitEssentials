# BitEssentials

一个帮助北理工人更方便地获取教学内容的工具（集）

# 功能

- [x] 保存用户会话到数据库
- [x] 乐学课程文件下载
- [ ] 导出课程表为ics格式
- [ ] 导出考试安排为ics格式
- [x] 自动查询成绩并推送
- [ ] 日历托管和自动更新

# Telegram机器人部署方法

- 安装依赖`pip install -r requirements.txt`
- 复制配置文件模板 `cp config_sample.json config.json` 后填写`config.json`
- 后台运行`nohup python main.py > bitessentials.log &`