#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接收端接口 v1.2 - 集成数据转发功能
功能：接收包含多个车辆状态字段的数据，并通过回调接口，
      将数据转换格式后实时转发到本地应用服务器。
"""

import socket
import json
import threading
import time
import requests  # <-- 新增：导入 requests 库

# ======================= 新增配置 =======================
# 定义数据将要被转发到的本地服务器地址
SERVER_PUSH_URL = "http://127.0.0.1:8000/api/push_data"


# =========================================================


class DataReceiver:
    """数据接收器 (代码与你提供的一致，无需修改)"""

    def __init__(self, relay_ipv6, relay_port):
        self.relay_address = (relay_ipv6, relay_port)
        self.socket = None
        self.running = False
        self.on_data_callback = None

    def connect(self):
        """连接到中转服务器"""
        try:
            addr_info = socket.getaddrinfo(self.relay_address[0], self.relay_address[1], 0, socket.SOCK_STREAM)
            sockaddr = None
            for res in addr_info:
                family, socktype, proto, _, sa = res
                if family == socket.AF_INET6:
                    sockaddr = sa
                    break
            if sockaddr is None:
                family, socktype, proto, _, sockaddr = addr_info[0]

            self.socket = socket.socket(family, socktype, proto)
            self.socket.connect(sockaddr)

            # 接收服务器询问并回复身份
            welcome = self.socket.recv(1024)
            print(f"Server welcome: {welcome.decode('utf-8', errors='ignore')}")
            self.socket.sendall(b"RECEIVER\n")

            print(f"✓ 已连接到中转服务器: {self.relay_address[0]}:{self.relay_address[1]}")
            return True
        except socket.gaierror as e:
            print(f"✗ 地址解析错误: {e}")
            return False
        except ConnectionRefusedError:
            print(f"✗ 连接被拒绝: 请检查服务器 {self.relay_address[0]}:{self.relay_address[1]} 是否正在运行并监听。")
            return False
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False

    def set_callback(self, callback):
        self.on_data_callback = callback

    def start(self):
        if not self.connect():
            return False
        self.running = True
        receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        receive_thread.start()
        print("开始接收数据...\n")
        return True

    def _receive_loop(self):
        buffer = ""
        try:
            while self.running:
                data = self.socket.recv(4096 * 2)
                if not data:
                    print("✗ 连接已断开 (服务器关闭或网络问题)")
                    break
                try:
                    buffer += data.decode('utf-8')
                except UnicodeDecodeError:
                    print("✗ 警告: 接收到无效UTF-8数据，已跳过。")
                    if '\n' in buffer:
                        _, buffer = buffer.split('\n', 1)
                    else:
                        buffer = ""
                    continue
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._process_message(line)
        except ConnectionResetError:
            print("✗ 连接被对方重置。")
        except OSError as e:
            if self.running:
                print(f"✗ Socket 错误: {e}")
        except Exception as e:
            if self.running:
                print(f"✗ 接收循环发生意外错误: {e}")
        finally:
            print("接收循环已停止。")
            self.running = False

    def _process_message(self, message):
        try:
            data_dict = json.loads(message)
            if self.on_data_callback:
                self.on_data_callback(data_dict)
            else:
                print(f"[{data_dict.get('timestamp')}] ID: {data_dict.get('vehicle_id')} | "
                      f"目标速度: {data_dict.get('target_speed_kmh', 'N/A')} km/h, "
                      f"实际速度: {data_dict.get('actual_speed_kmh', 'N/A')} km/h")
        except json.JSONDecodeError as e:
            print(f"\n✗ JSON 解析失败: {e} | 原始消息: {message[:100]}...")
        except Exception as e:
            print(f"\n✗ 处理消息时发生错误: {e} | 消息: {message[:100]}...")

    def stop(self):
        print("正在停止接收器...")
        self.running = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except OSError:
                pass
            self.socket = None
        print("接收器已停止。")


# ============ 使用示例 (已修改) ============

# 为了提升性能，创建一个可复用的 Session 对象
# 这个对象将在 my_data_handler 回调函数中被使用
session = requests.Session()


def my_data_handler(data_dict):
    """
    用户自定义的数据处理函数。
    功能：接收字典数据，转换格式，并通过HTTP POST请求转发出去。
    """
    # 1. --- 从原始数据中安全地提取所需字段 ---
    lat = data_dict.get('latitude')
    lon = data_dict.get('longitude')
    vehicle_id = data_dict.get('vehicle_id')

    # 如果核心数据缺失，则直接返回，不进行转发
    if lat is None or lon is None or vehicle_id is None:
        return

    # 2. --- 将数据构造成目标格式 (与 external_simulator.py 一致) ---
    forward_payload = {
        "messageType": "vehicle_position",
        "data": {
            "trainDeviceCode": vehicle_id,
            "lat": float(lat),
            "lon": float(lon),
            # 使用 actual_speed_kmh 作为速度来源，如果不存在则默认为0
            "speed": round(float(data_dict.get('actual_speed_kmh', 0))),
        }
    }

    # 3. --- 尝试通过 HTTP POST 转发数据 ---
    try:
        response = session.post(SERVER_PUSH_URL, json=forward_payload, timeout=2)

        # 4. --- 根据转发结果，在终端打印优雅的实时日志 ---
        status_char = "✓" if response.status_code == 200 else "✗"
        data_to_log = forward_payload['data']

        # 使用 \r 和 end="" 实现单行刷新日志，避免刷屏
        log_message = (
            f"\r[{status_char}] ID: {data_to_log['trainDeviceCode']} | "
            f"Lat: {data_to_log['lat']:.6f}, Lon: {data_to_log['lon']:.6f} | "
            f"Speed: {data_to_log['speed']} km/h -> Forwarding..."
        )

        if response.status_code == 200:
            print(log_message, end="", flush=True)
        else:
            # 如果失败，则换行打印详细错误信息
            try:
                error_details = response.json().get('message', response.reason)
            except json.JSONDecodeError:
                error_details = response.text.strip()

            print(f"\n{log_message.replace('-> Forwarding...', '-> FAILED!')} "
                  f"Status: {response.status_code}. Reason: {error_details}")

    except requests.exceptions.RequestException:
        # 如果本地服务器无法连接，打印提示信息
        print(f"\n✗ [转发器] 无法连接到本地服务器({SERVER_PUSH_URL})。请确认目标应用正在运行。")
        time.sleep(2)  # 暂停一下，避免因连接失败而疯狂刷屏


def example_usage():
    """使用示例"""
    receiver = DataReceiver(
        relay_ipv6="43.143.207.201",
        relay_port=8888
    )

    # 关键：将我们重写的、具备转发功能的回调函数设置给接收器
    receiver.set_callback(my_data_handler)

    if receiver.start():
        print("按 Ctrl+C 停止程序。")
        try:
            while receiver.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到停止信号 (Ctrl+C)...")
        except Exception as e:
            print(f"\n主循环发生错误: {e}")
        finally:
            receiver.stop()
    else:
        print("接收器未能启动。")


if __name__ == "__main__":
    print("=" * 60)
    print("    数据接收与转发接口 v1.2 - 示例程序")
    print("=" * 60)
    print(f"将从远程服务器接收数据，并转发到: {SERVER_PUSH_URL}")
    print()
    example_usage()
    print("\n程序结束。")