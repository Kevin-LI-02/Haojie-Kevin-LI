"""
实时数据推送模块
用于EYES-T系统直接推送报警数据到AI Assistant
"""

import requests
import json
import threading
from datetime import datetime

class RealtimePusher:
    """实时数据推送器"""
    
    def __init__(self, ai_assistant_url="http://localhost:5000"):
        self.ai_assistant_url = ai_assistant_url
        self.push_api = f"{ai_assistant_url}/api/alarms/push"
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def push_alarm_async(self, alarm_type, data_dict):
        """异步推送报警数据（不阻塞主线程）"""
        thread = threading.Thread(target=self._push_alarm, args=(alarm_type, data_dict))
        thread.daemon = True
        thread.start()
    
    def _push_alarm(self, alarm_type, data_dict):
        """推送报警数据到AI Assistant"""
        try:
            payload = {
                'alarm_type': alarm_type,
                'data': data_dict,
                'timestamp': datetime.now().isoformat()
            }
            
            response = self.session.post(
                self.push_api,
                json=payload,
                timeout=2  # 2秒超时，避免阻塞
            )
            
            if response.status_code == 200:
                # print(f"✓ 数据推送成功: {alarm_type}")
                pass
            else:
                print(f"✗ 数据推送失败: {response.status_code}")
                
        except requests.exceptions.Timeout:
            # 超时静默失败，不影响主程序
            pass
        except requests.exceptions.ConnectionError:
            # 连接失败静默失败（AI Assistant可能未启动）
            pass
        except Exception as e:
            print(f"推送异常: {e}")


# 全局单例
_pusher_instance = None

def get_pusher():
    """获取推送器单例"""
    global _pusher_instance
    if _pusher_instance is None:
        _pusher_instance = RealtimePusher()
    return _pusher_instance


def push_alarmlist_data(date_time, area, sub_area, object_name, text, suggested_action):
    """推送报警列表数据"""
    pusher = get_pusher()
    data = {
        'date_time': date_time,
        'area': area,
        'sub_area': sub_area,
        'object': object_name,
        'text': text,
        'suggested_action': suggested_action
    }
    pusher.push_alarm_async('Alarm List', data)


def push_turnout_data(turnout_id, timestamp_text, status, throw_time, feedback_text):
    """推送道岔数据"""
    pusher = get_pusher()
    data = {
        'turnout_id': turnout_id,
        'timestamp': timestamp_text,
        'status': status,
        'throw_time': throw_time,
        'text': feedback_text
    }
    pusher.push_alarm_async('Turnout', data)


def push_power_data(dt, id_, desc, status):
    """推送电源数据"""
    pusher = get_pusher()
    data = {
        'date_time': dt,
        'id': id_,
        'description': desc,
        'status': status
    }
    pusher.push_alarm_async('Power', data)


def push_train_data(train_id, date_time, status, delay_text, dwell_time_text, location, station_text, line_status):
    """推送列车数据"""
    pusher = get_pusher()
    data = {
        'train_id': train_id,
        'date_time': date_time,
        'status': status,
        'delay': delay_text,
        'dwell': dwell_time_text,
        'location': location,
        'station': station_text,
        'door': line_status
    }
    pusher.push_alarm_async('Train', data)


def push_route_check_data(timestamp, train_type, shs_result, lmc_result, low_result, check_result, alert=""):
    """推送进路检查数据"""
    pusher = get_pusher()
    data = {
        'timestamp': timestamp,
        'train_id_type': train_type,
        'shs_route': shs_result,
        'lmc_route': lmc_result,
        'low_route': low_result,
        'route_check': check_result,
        'alert': alert
    }
    pusher.push_alarm_async('Route Check', data)

