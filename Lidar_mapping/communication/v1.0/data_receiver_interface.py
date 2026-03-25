#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接收端接口 v1.1
功能：接收包含多个车辆状态字段的数据，并提供回调接口，用户可以自定义数据处理逻辑。
"""

import socket
import json
import threading
import time


class DataReceiver:
    """数据接收器"""

    def __init__(self, relay_ipv6, relay_port):
        """
        初始化接收器
        :param relay_ipv6: 中转服务器地址 (域名或IPv4/IPv6)
        :param relay_port: 中转服务器端口
        """
        self.relay_address = (relay_ipv6, relay_port)
        self.socket = None
        self.running = False
        self.on_data_callback = None

    def connect(self):
        """连接到中转服务器"""
        try:
            # 使用 getaddrinfo 自动判断IP协议版本
            addr_info = socket.getaddrinfo(self.relay_address[0], self.relay_address[1], 0, socket.SOCK_STREAM)
            # --- 确保我们能处理 AF_INET6 ---
            # family, socktype, proto, _, sockaddr = addr_info[0] # 可能选到 IPv4
            # 优先选择 IPv6 (如果服务器支持)
            sockaddr = None
            for res in addr_info:
                family, socktype, proto, _, sa = res
                # 简单示例：优先IPv6，否则用第一个结果
                if family == socket.AF_INET6:
                    sockaddr = sa
                    break
            if sockaddr is None: # 如果没找到 IPv6, 使用第一个结果
                 family, socktype, proto, _, sockaddr = addr_info[0]

            self.socket = socket.socket(family, socktype, proto)
            # ---------------------------------------------
            self.socket.connect(sockaddr)

            # 接收服务器询问并回复身份 (假设服务器需要)
            # welcome = self.socket.recv(1024)
            # print(f"Server welcome: {welcome.decode()}") # Optional: print welcome
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
        """
        设置数据回调函数
        :param callback: 回调函数，参数为一个包含所有接收到的数据的字典
                         例如: {'timestamp': '...', 'link_id': '...', 'offset_m': ..., ...}
        """
        self.on_data_callback = callback

    def start(self):
        """启动接收"""
        if not self.connect():
            return False

        self.running = True
        receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        receive_thread.start()

        print("开始接收数据...\n")
        return True

    def _receive_loop(self):
        """接收数据循环"""
        buffer = ""

        try:
            while self.running:
                # 增加接收缓冲区大小以匹配C代码的可能发送大小
                data = self.socket.recv(4096 * 2) # 增加到 8KB
                if not data:
                    print("✗ 连接已断开 (服务器关闭或网络问题)")
                    break

                # 尝试解码，如果失败则跳过问题数据块
                try:
                    buffer += data.decode('utf-8')
                except UnicodeDecodeError:
                    print("✗ 警告: 接收到无效UTF-8数据，已跳过。")
                    # 尝试找到下一个换行符，丢弃之前的部分
                    if '\n' in buffer:
                        _, buffer = buffer.split('\n', 1)
                    else:
                        buffer = "" # 如果没有换行符，丢弃所有内容
                    continue

                # 处理缓冲区中所有完整的 JSON 消息 (以换行符分隔)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip(): # 忽略空行
                        self._process_message(line)

        except ConnectionResetError:
             print("✗ 连接被对方重置。")
        except OSError as e: # Catch other socket errors like closed connection
            if self.running: # Only print if we expected to be running
                 print(f"✗ Socket 错误: {e}")
        except Exception as e:
            if self.running:
                print(f"✗ 接收循环发生意外错误: {e}")
        finally:
            print("接收循环已停止。")
            self.running = False
            # 可以在这里添加自动重连逻辑

    def _process_message(self, message):
        """处理接收到的单条 JSON 消息"""
        try:
            # 解析整条消息为字典
            data_dict = json.loads(message)

            # 如果设置了回调函数，则调用它
            if self.on_data_callback:
                # 将完整的字典传递给回调
                self.on_data_callback(data_dict)
            else:
                # --- 修改：默认打印语句，使用新的速度字段名 ---
                print(f"[{data_dict.get('timestamp')}] ID: {data_dict.get('vehicle_id')} | "
                      f"目标速度: {data_dict.get('target_speed_kmh', 'N/A')} km/h, " # <-- 更新字段名
                      f"实际速度: {data_dict.get('actual_speed_kmh', 'N/A')} km/h") # <-- 更新字段名

        except json.JSONDecodeError as e:
            print(f"✗ JSON 解析失败: {e} | 原始消息: {message[:100]}...") # 只显示部分消息
        except Exception as e:
            print(f"✗ 处理消息时发生错误: {e} | 消息: {message[:100]}...")

    def stop(self):
        """停止接收并关闭socket"""
        print("正在停止接收器...")
        self.running = False
        if self.socket:
            try:
                # 关闭socket以中断接收线程的 recv 调用
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except OSError as e:
                 # Ignore errors if the socket is already closed
                 # print(f"关闭 socket 时出错: {e}")
                 pass
            self.socket = None # 清理 socket 对象
        print("接收器已停止。")


# ============ 使用示例 ============

def my_data_handler(data_dict):
    """
    用户自定义的数据处理函数 - 已更新以处理所有字段
    :param data_dict: 包含所有车辆数据的字典
    """
    # --- 修改：使用 .get() 提取所有字段，提供默认值以防字段缺失 ---
    timestamp = data_dict.get('timestamp', 'N/A')
    vehicle_id = data_dict.get('vehicle_id', 'N/A')
    link_id = data_dict.get('link_id', 'N/A')
    offset_m = data_dict.get('offset_m', 0.0)
    longitude = data_dict.get('longitude', 0.0)
    latitude = data_dict.get('latitude', 0.0)
    heading_deg = data_dict.get('heading_deg', 0.0)           # 新增
    vehicle_mode = data_dict.get('vehicle_mode', -1)          # 新增 (-1 表示未知)
    battery_soc = data_dict.get('battery_soc', 0.0)           # 新增
    accel_m_s2 = data_dict.get('accel_m_s2', 0.0)             # 新增
    target_speed = data_dict.get('target_speed_kmh', 0.0)     # 更新字段名
    actual_speed = data_dict.get('actual_speed_kmh', 0.0)     # 更新字段名
    total_displacement_m = data_dict.get('total_displacement_m', 0.0) # 新增

    # --- 修改：更新打印语句以包含更多信息 ---
    print(f"[{timestamp}] 处理: {vehicle_id} | Link='{link_id}' Off={offset_m:.2f}m | "
          f"坐标=({latitude:.6f}, {longitude:.6f}) Hdg={heading_deg:.1f}° | "
          f"模式={vehicle_mode} 电量={battery_soc:.1f}% | "
          f"速度(目标/实际)={target_speed:.2f}/{actual_speed:.2f}km/h | "
          f"加速度={accel_m_s2:.2f}m/s² | 总位移={total_displacement_m:.1f}m")

    # 在这里添加你的进一步处理逻辑:
    # - 保存到文件或数据库
    # - 更新图形用户界面 (GUI)
    # - 进行实时分析或决策
    # - 将数据转发给其他系统


def example_usage():
    """使用示例"""

    # 1. 创建接收器实例 (确保地址和端口与 C 代码匹配)
    receiver = DataReceiver(
        relay_ipv6="43.143.207.201",  # 中转服务器地址
        relay_port=8888              # 中转服务器端口
    )

    # 2. (可选) 设置你的自定义回调函数
    receiver.set_callback(my_data_handler)

    # 3. 启动接收器 (它将在后台线程中运行)
    if receiver.start():
        print("按 Ctrl+C 停止程序。")
        try:
            # 让主线程保持活动状态，以便后台线程可以继续运行
            while receiver.running: # 检查运行状态
                time.sleep(1) # 每秒检查一次
        except KeyboardInterrupt:
            print("\n收到停止信号 (Ctrl+C)...")
        except Exception as e:
            print(f"\n主循环发生错误: {e}")
        finally:
             # 4. 确保停止接收器
             receiver.stop()
    else:
        print("接收器未能启动。")


if __name__ == "__main__":
    print("=" * 60)
    print("    数据接收端接口 v1.1 - 示例程序")
    print("=" * 60)
    print("将连接到中转服务器并接收车辆数据。")
    print()
    example_usage()
    print("\n程序结束。")