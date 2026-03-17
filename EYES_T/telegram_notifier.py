"""
Telegram Bot 通知模块
用于替代企业微信 Webhook，将报警信息发送到 Telegram 群组
"""

import requests
import json
from typing import Optional, Dict, List


class TelegramNotifier:
    """Telegram Bot 通知器"""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        初始化 Telegram 通知器
        
        Args:
            bot_token: Telegram Bot Token (从 @BotFather 获取)
            chat_id: 群组 Chat ID (负数，如 -1001234567890)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        发送文本消息到 Telegram 群组
        
        Args:
            message: 消息内容
            parse_mode: 解析模式 ("HTML", "Markdown", 或 None)
            
        Returns:
            发送是否成功
        """
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print("✅ Telegram 通知发送成功")
                return True
            else:
                print(f"❌ Telegram 通知发送失败: {response.status_code}")
                print(f"响应内容: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 发送 Telegram 通知时出错: {e}")
            return False
    
    def send_alarm_notification(self, alarm_data: Dict) -> bool:
        """
        发送报警通知（格式化）
        
        Args:
            alarm_data: 报警数据字典，包含以下字段：
                - timestamp: 时间戳
                - alarm_type: 报警类型
                - station: 站点
                - description: 描述
                - severity: 严重程度
                - 其他自定义字段
                
        Returns:
            发送是否成功
        """
        # 构建格式化的 HTML 消息
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }
        
        severity = alarm_data.get("severity", "medium").lower()
        emoji = severity_emoji.get(severity, "⚠️")
        
        message = f"""
{emoji} <b>EYES-T 报警通知</b> {emoji}

<b>时间：</b>{alarm_data.get('timestamp', 'N/A')}
<b>类型：</b>{alarm_data.get('alarm_type', 'N/A')}
<b>站点：</b>{alarm_data.get('station', 'N/A')}
<b>严重程度：</b>{severity.upper()}
<b>描述：</b>{alarm_data.get('description', 'N/A')}
"""
        
        # 添加其他字段
        for key, value in alarm_data.items():
            if key not in ['timestamp', 'alarm_type', 'station', 'severity', 'description']:
                message += f"<b>{key}：</b>{value}\n"
        
        message += "\n⚡ 请及时处理"
        
        return self.send_message(message)
    
    def send_train_notification(self, train_data: Dict) -> bool:
        """发送列车报警通知"""
        message = f"""
🚂 <b>列车报警</b>

<b>时间：</b>{train_data.get('timestamp', 'N/A')}
<b>车次：</b>{train_data.get('train_id', 'N/A')}
<b>状态：</b>{train_data.get('status', 'N/A')}
<b>延误：</b>{train_data.get('delay', 'N/A')}
<b>停留时间：</b>{train_data.get('dwell_time', 'N/A')}
<b>位置：</b>{train_data.get('location', 'N/A')}
<b>站点：</b>{train_data.get('station', 'N/A')}
<b>车门：</b>{train_data.get('door_status', 'N/A')}

⚡ 请及时处理
"""
        return self.send_message(message)
    
    def send_turnout_notification(self, turnout_data: Dict) -> bool:
        """发送道岔报警通知"""
        message = f"""
🔀 <b>道岔报警</b>

<b>时间：</b>{turnout_data.get('timestamp', 'N/A')}
<b>道岔ID：</b>{turnout_data.get('turnout_id', 'N/A')}
<b>状态：</b>{turnout_data.get('status', 'N/A')}
<b>转换时间：</b>{turnout_data.get('throw_time', 'N/A')}
<b>描述：</b>{turnout_data.get('text', 'N/A')}

⚡ 请及时处理
"""
        return self.send_message(message)
    
    def send_power_notification(self, power_data: Dict) -> bool:
        """发送电源报警通知"""
        message = f"""
⚡ <b>电源系统报警</b>

<b>时间：</b>{power_data.get('timestamp', 'N/A')}
<b>设备ID：</b>{power_data.get('id', 'N/A')}
<b>描述：</b>{power_data.get('description', 'N/A')}
<b>状态：</b>{power_data.get('status', 'N/A')}

⚡ 请及时处理
"""
        return self.send_message(message)
    
    def send_alarmlist_notification(self, alarm_data: Dict) -> bool:
        """发送告警列表通知"""
        # 检查优先级
        priority = alarm_data.get('priority', 3)
        priority_emoji = {
            1: "🔴 高优先级",
            2: "🟠 中优先级",
            3: "🟡 低优先级"
        }
        
        message = f"""
📋 <b>系统告警</b>

{priority_emoji.get(priority, '⚠️')}

<b>时间：</b>{alarm_data.get('date_time', 'N/A')}
<b>区域：</b>{alarm_data.get('area', 'N/A')}
<b>子区域：</b>{alarm_data.get('sub_area', 'N/A')}
<b>对象：</b>{alarm_data.get('object', 'N/A')}
<b>内容：</b>{alarm_data.get('text', 'N/A')}
"""
        
        # 如果有操作建议，添加到消息中
        if 'action' in alarm_data and alarm_data['action']:
            message += f"\n<b>🔧 处置建议：</b>\n{alarm_data['action']}"
        
        message += "\n\n⚡ 请及时处理"
        
        return self.send_message(message)
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        url = f"{self.base_url}/getMe"
        
        try:
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                bot_info = response.json()
                bot_name = bot_info.get('result', {}).get('username', 'Unknown')
                print(f"✅ Telegram Bot 连接成功！Bot 用户名: @{bot_name}")
                return True
            else:
                print(f"❌ Telegram Bot 连接失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 测试连接时出错: {e}")
            return False


# ============== 使用示例 ==============

def example_usage():
    """使用示例"""
    
    # 1. 初始化通知器
    bot_token = "YOUR_BOT_TOKEN"  # 替换为你的 Bot Token
    chat_id = "YOUR_CHAT_ID"      # 替换为你的群组 Chat ID
    
    notifier = TelegramNotifier(bot_token, chat_id)
    
    # 2. 测试连接
    if not notifier.test_connection():
        print("请检查 Bot Token 和网络连接")
        return
    
    # 3. 发送简单消息
    notifier.send_message("🔔 EYES-T 系统已启动")
    
    # 4. 发送列车报警
    train_alarm = {
        "timestamp": "2025-12-01 14:30:00",
        "train_id": "JM0602",
        "status": "AM direction A",
        "delay": "First train: delay > 3:00 minute",
        "dwell_time": "+05:30",
        "location": "Platform 2",
        "station": "Lo Wu",
        "door_status": "Berthed, Door closed"
    }
    notifier.send_train_notification(train_alarm)
    
    # 5. 发送道岔报警
    turnout_alarm = {
        "timestamp": "2025-12-01 14:35:00",
        "turnout_id": "5903",
        "status": "Failed",
        "throw_time": "8.5s",
        "text": "Point did not move from right in time"
    }
    notifier.send_turnout_notification(turnout_alarm)
    
    # 6. 发送告警列表通知
    alarmlist_data = {
        "date_time": "2025-12-01 14:40:00",
        "area": "Station A",
        "sub_area": "Track 2",
        "object": "Signal S8",
        "text": "S8: Point did not move from right in time",
        "priority": 1,
        "action": "1. 立即检查道岔状态\n2. 联系维护人员\n3. 必要时切换备用线路"
    }
    notifier.send_alarmlist_notification(alarmlist_data)


if __name__ == "__main__":
    print("=" * 60)
    print("Telegram 通知模块测试")
    print("=" * 60)
    print("\n请先设置你的 Bot Token 和 Chat ID")
    print("然后取消注释下面的代码行来测试\n")
    # example_usage()

