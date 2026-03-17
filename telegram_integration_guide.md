# Telegram Bot 集成指南

## 📋 目录

1. [创建 Telegram Bot](#1-创建-telegram-bot)
2. [获取群组 Chat ID](#2-获取群组-chat-id)
3. [安装依赖](#3-安装依赖)
4. [配置系统](#4-配置系统)
5. [代码集成](#5-代码集成)
6. [测试验证](#6-测试验证)
7. [常见问题](#7-常见问题)

---

## 1. 创建 Telegram Bot

### 步骤 1.1: 安装 Telegram

- 下载并安装 Telegram Desktop 或使用手机版
- 注册并登录账号

### 步骤 1.2: 创建 Bot

1. **搜索 @BotFather**（Telegram 官方 Bot）
2. **发送命令**：`/newbot`
3. **设置 Bot 显示名称**（例如：`EYES-T Alert Bot`）
4. **设置 Bot 用户名**（例如：`eyest_alert_bot`，必须以 `_bot` 或 `Bot` 结尾）
5. **保存 Bot Token**（格式如：`7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`）

⚠️ **重要**：Bot Token 相当于密码，不要泄露！

---

## 2. 获取群组 Chat ID

### 方法一：通过 Bot 获取（推荐）

1. **创建一个 Telegram 群组**
2. **将你的 Bot 添加到群组**
3. **在群组中发送任意消息**（例如：`/start`）
4. **在浏览器访问**：
   ```
   https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates
   ```
   
5. **查找返回的 JSON 中的 Chat ID**：
   ```json
   {
     "ok": true,
     "result": [
       {
         "message": {
           "chat": {
             "id": -1001234567890,  ← 这就是你的 Chat ID（负数）
             "title": "EYES-T 报警群组",
             "type": "group"
           }
         }
       }
     ]
   }
   ```

### 方法二：使用 Python 脚本获取

创建一个临时脚本 `get_chat_id.py`：

```python
import requests

bot_token = "YOUR_BOT_TOKEN"  # 替换为你的 Bot Token
url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

response = requests.get(url)
data = response.json()

print("=" * 60)
print("Chat ID 列表：")
print("=" * 60)

for update in data.get('result', []):
    if 'message' in update:
        chat = update['message']['chat']
        print(f"群组名称: {chat.get('title', 'N/A')}")
        print(f"Chat ID: {chat['id']}")
        print(f"类型: {chat['type']}")
        print("-" * 60)
```

运行脚本：
```bash
python get_chat_id.py
```

---

## 3. 安装依赖

Telegram 通知只需要 `requests` 库（已包含在现有依赖中）。

如果需要额外安装：
```bash
pip install requests
```

---

## 4. 配置系统

### 4.1 修改 `default account.csv`

在 CSV 文件中添加 Telegram 配置：

```csv
Parameter,Content
WeChat Webhook URL,https://qyapi.weixin.qq.com/...（保留作为备用）
Telegram Bot Token,7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
Telegram Chat ID,-1001234567890
Receiver Email,eal.bjtu@gmail.com
Smtp server,smtp.163.com
Smtp port,465
Sender email,lihaojie0044@163.com
Sender password,AQri6kUXQ4tK9nNC
```

### 4.2 创建配置文件（推荐）

创建 `telegram_config.json`：

```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "chat_id": "YOUR_CHAT_ID",
  "enable_html": true,
  "enable_notifications": true
}
```

---

## 5. 代码集成

### 5.1 在 `alarmlist.py` 中集成

在文件开头添加导入：

```python
from telegram_notifier import TelegramNotifier
```

在 `__init__` 方法中初始化：

```python
def __init__(self, ui):
    super().__init__()
    # ... 现有代码 ...
    
    # 初始化 Telegram 通知器
    telegram_token = self.settings.get("Telegram Bot Token")
    telegram_chat_id = self.settings.get("Telegram Chat ID")
    
    if telegram_token and telegram_chat_id:
        self.telegram_notifier = TelegramNotifier(telegram_token, telegram_chat_id)
        # 测试连接
        if self.telegram_notifier.test_connection():
            print("✅ Telegram 通知器初始化成功")
        else:
            print("⚠️ Telegram 通知器初始化失败，请检查配置")
    else:
        self.telegram_notifier = None
        print("⚠️ Telegram 配置未设置")
```

### 5.2 替换企业微信通知

**原有代码**（企业微信）：
```python
def send_notification_auto(self, ocr_results):
    # ... 构建消息 ...
    
    webhook_url = self.settings.get("WeChat Webhook URL")
    payload = {"msgtype": "text", "text": {"content": message}}
    response = requests.post(webhook_url, json=payload)
```

**修改为** Telegram：
```python
def send_notification_auto(self, ocr_results):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    matched_text = ocr_results[4]
    
    # 构建报警数据
    alarm_data = {
        "date_time": ocr_results[0],
        "area": ocr_results[1],
        "sub_area": ocr_results[2],
        "object": ocr_results[3],
        "text": ocr_results[4],
        "priority": self.alerts_priority.get(matched_text, {}).get("priority", 3),
        "action": self.alerts_priority.get(matched_text, {}).get("action", "无对应操作建议")
    }
    
    # 发送 Telegram 通知
    if self.telegram_notifier:
        success = self.telegram_notifier.send_alarmlist_notification(alarm_data)
        if success:
            print("✅ Telegram 通知发送成功")
        else:
            print("❌ Telegram 通知发送失败")
    else:
        print("⚠️ Telegram 通知器未初始化")
```

### 5.3 在 `train.py` 中集成

```python
def send_notification_auto(self, train_id, timestamp, status, delay, dwell_time, location, station, door_status):
    # 构建列车报警数据
    train_data = {
        "timestamp": timestamp,
        "train_id": train_id,
        "status": status,
        "delay": delay,
        "dwell_time": dwell_time,
        "location": location,
        "station": station,
        "door_status": door_status
    }
    
    # 发送 Telegram 通知
    if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
        self.telegram_notifier.send_train_notification(train_data)
```

### 5.4 在 `turnout.py` 中集成

```python
def send_notification_auto(self, turnout_id, timestamp, status, throw_time, text):
    # 构建道岔报警数据
    turnout_data = {
        "timestamp": timestamp,
        "turnout_id": turnout_id,
        "status": status,
        "throw_time": throw_time,
        "text": text
    }
    
    # 发送 Telegram 通知
    if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
        self.telegram_notifier.send_turnout_notification(turnout_data)
```

### 5.5 在 `power.py` 中集成

```python
def send_notification_auto(self, timestamp, id, description, status):
    # 构建电源报警数据
    power_data = {
        "timestamp": timestamp,
        "id": id,
        "description": description,
        "status": status
    }
    
    # 发送 Telegram 通知
    if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
        self.telegram_notifier.send_power_notification(power_data)
```

---

## 6. 测试验证

### 6.1 创建测试脚本

创建 `test_telegram.py`：

```python
from telegram_notifier import TelegramNotifier

# 替换为你的实际配置
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

def test_telegram():
    print("开始测试 Telegram 通知...")
    
    # 1. 初始化
    notifier = TelegramNotifier(BOT_TOKEN, CHAT_ID)
    
    # 2. 测试连接
    print("\n[1/4] 测试连接...")
    if not notifier.test_connection():
        print("❌ 连接失败，请检查 Token 和网络")
        return
    
    # 3. 测试简单消息
    print("\n[2/4] 测试简单消息...")
    notifier.send_message("🔔 这是一条测试消息")
    
    # 4. 测试告警通知
    print("\n[3/4] 测试告警通知...")
    alarm_data = {
        "date_time": "2025-12-01 15:00:00",
        "area": "测试区域",
        "sub_area": "子区域 A",
        "object": "测试对象",
        "text": "这是一条测试告警",
        "priority": 1,
        "action": "测试操作建议"
    }
    notifier.send_alarmlist_notification(alarm_data)
    
    # 5. 测试列车通知
    print("\n[4/4] 测试列车通知...")
    train_data = {
        "timestamp": "2025-12-01 15:05:00",
        "train_id": "TEST001",
        "status": "测试状态",
        "delay": "无延误",
        "dwell_time": "+00:30",
        "location": "Platform 1",
        "station": "Test Station",
        "door_status": "测试中"
    }
    notifier.send_train_notification(train_data)
    
    print("\n✅ 测试完成！请检查 Telegram 群组")

if __name__ == "__main__":
    test_telegram()
```

运行测试：
```bash
python test_telegram.py
```

### 6.2 验证清单

- [ ] Bot 已创建并获取 Token
- [ ] 群组已创建并添加 Bot
- [ ] Chat ID 已正确获取
- [ ] 配置文件已更新
- [ ] 测试连接成功
- [ ] 能够接收测试消息
- [ ] 消息格式正确显示

---

## 7. 常见问题

### Q1: Bot 无法发送消息到群组

**可能原因**：
- Bot 未被添加到群组
- Bot 没有发送消息的权限
- Chat ID 不正确（应该是负数）

**解决方案**：
1. 确认 Bot 在群组成员列表中
2. 给 Bot 管理员权限
3. 重新获取 Chat ID

### Q2: 网络连接错误

**可能原因**：
- 无法访问 Telegram API（可能需要代理）
- 防火墙阻止

**解决方案**：
```python
# 设置代理
import os
os.environ['HTTP_PROXY'] = 'http://your-proxy:port'
os.environ['HTTPS_PROXY'] = 'http://your-proxy:port'
```

或在代码中：
```python
proxies = {
    'http': 'http://your-proxy:port',
    'https': 'http://your-proxy:port'
}
response = requests.post(url, json=payload, proxies=proxies)
```

### Q3: 消息发送频率限制

Telegram 限制：
- 每秒最多 30 条消息
- 每分钟最多向同一群组发送 20 条消息

**解决方案**：
- 添加消息队列
- 合并相似告警
- 添加发送延迟

### Q4: 想要保留企业微信和 Telegram 双通道

```python
def send_notification_auto(self, alarm_data):
    # 同时发送到两个平台
    
    # 发送到 Telegram
    if self.telegram_notifier:
        self.telegram_notifier.send_alarmlist_notification(alarm_data)
    
    # 发送到企业微信（备用）
    if self.settings.get("WeChat Webhook URL"):
        webhook_url = self.settings["WeChat Webhook URL"]
        message = self.format_wechat_message(alarm_data)
        payload = {"msgtype": "text", "text": {"content": message}}
        requests.post(webhook_url, json=payload)
```

---

## 8. 高级功能

### 8.1 添加按钮交互

```python
def send_message_with_buttons(self, message: str, buttons: List[List[Dict]]):
    """发送带按钮的消息"""
    url = f"{self.base_url}/sendMessage"
    
    payload = {
        "chat_id": self.chat_id,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": buttons
        }
    }
    
    response = requests.post(url, json=payload)
    return response.status_code == 200

# 使用示例
buttons = [
    [
        {"text": "✅ 已处理", "callback_data": "resolved"},
        {"text": "⏳ 处理中", "callback_data": "processing"}
    ],
    [
        {"text": "❌ 需要支援", "callback_data": "need_help"}
    ]
]
notifier.send_message_with_buttons("报警通知", buttons)
```

### 8.2 发送图片

```python
def send_photo(self, photo_path: str, caption: str = ""):
    """发送图片"""
    url = f"{self.base_url}/sendPhoto"
    
    with open(photo_path, 'rb') as photo:
        files = {'photo': photo}
        data = {
            'chat_id': self.chat_id,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=data, files=files)
    
    return response.status_code == 200
```

### 8.3 发送文件

```python
def send_document(self, file_path: str, caption: str = ""):
    """发送文件（如 CSV 报表）"""
    url = f"{self.base_url}/sendDocument"
    
    with open(file_path, 'rb') as doc:
        files = {'document': doc}
        data = {
            'chat_id': self.chat_id,
            'caption': caption
        }
        response = requests.post(url, data=data, files=files)
    
    return response.status_code == 200
```

---

## 9. 其他替代方案对比

### Discord Webhook（次推荐）

**优势**：实现极简单

```python
import requests

webhook_url = "YOUR_DISCORD_WEBHOOK_URL"
message = {
    "content": "报警消息",
    "embeds": [{
        "title": "🚨 EYES-T 报警",
        "description": "列车超速",
        "color": 15158332,  # 红色
        "fields": [
            {"name": "时间", "value": "2025-12-01 15:00:00"},
            {"name": "站点", "value": "LMC"}
        ]
    }]
}
requests.post(webhook_url, json=message)
```

### 钉钉 DingTalk

```python
import requests
import time
import hmac
import hashlib
import base64
import urllib.parse

webhook = "YOUR_DINGTALK_WEBHOOK"
secret = "YOUR_SECRET"

timestamp = str(round(time.time() * 1000))
secret_enc = secret.encode('utf-8')
string_to_sign = f'{timestamp}\n{secret}'
string_to_sign_enc = string_to_sign.encode('utf-8')
hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

url = f"{webhook}&timestamp={timestamp}&sign={sign}"

message = {
    "msgtype": "text",
    "text": {"content": "报警消息"}
}

requests.post(url, json=message)
```

---

## 10. 总结

### Telegram Bot 优势：

✅ **免费无限制**  
✅ **API 简单稳定**  
✅ **支持富文本、按钮、图片**  
✅ **跨平台（手机、电脑、网页）**  
✅ **消息可追溯、可搜索**  
✅ **无需企业认证**  

### 推荐使用场景：

- ✅ 实时报警通知
- ✅ 系统状态更新  
- ✅ 数据报表推送  
- ✅ 团队协作沟通  

---

**完成以上步骤后，您的 EYES-T 系统就可以通过 Telegram 发送报警通知了！** 🎉

如有问题，请参考 [Telegram Bot API 官方文档](https://core.telegram.org/bots/api)

