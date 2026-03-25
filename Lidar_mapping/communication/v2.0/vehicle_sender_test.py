#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
车辆发送端测试程序 v1.0 - 用于通信质量测试
功能：模拟车辆端发送数据，包含序列号和时间戳用于通信质量评估
"""

import socket
import json
import time
import random
from datetime import datetime


class VehicleSenderTest:
    """测试车辆发送器"""

    def __init__(self, relay_address, relay_port, vehicle_id="TEST_VEHICLE_001", send_interval=0.1):
        """
        初始化测试发送器
        :param relay_address: 中转服务器地址
        :param relay_port: 中转服务器端口
        :param vehicle_id: 车辆ID
        :param send_interval: 发送间隔（秒）
        """
        self.relay_address = (relay_address, relay_port)
        self.vehicle_id = vehicle_id
        self.send_interval = send_interval
        self.socket = None
        self.running = False

        # 用于模拟的状态变量
        self.sequence_number = 0  # 序列号，用于丢包检测
        self.latitude = 39.9042  # 初始纬度（北京）
        self.longitude = 116.4074  # 初始经度
        self.heading = 0.0
        self.speed = 0.0
        self.displacement = 0.0

    def connect(self):
        """连接到中转服务器"""
        try:
            # 使用 getaddrinfo 自动判断IP协议版本
            addr_info = socket.getaddrinfo(
                self.relay_address[0],
                self.relay_address[1],
                0,
                socket.SOCK_STREAM
            )

            # 优先选择 IPv6
            sockaddr = None
            for res in addr_info:
                family, socktype, proto, _, sa = res
                if family == socket.AF_INET6:
                    sockaddr = sa
                    break

            if sockaddr is None:  # 如果没有 IPv6, 使用第一个结果
                family, socktype, proto, _, sockaddr = addr_info[0]

            self.socket = socket.socket(family, socktype, proto)
            self.socket.connect(sockaddr)

            # 接收服务器询问并回复身份
            welcome = self.socket.recv(1024)
            print(f"服务器消息: {welcome.decode().strip()}")

            # 发送身份标识
            self.socket.sendall(b"VEHICLE\n")

            print(f"✓ 已连接到中转服务器: {self.relay_address[0]}:{self.relay_address[1]}")
            print(f"✓ 车辆ID: {self.vehicle_id}")
            print(f"✓ 发送间隔: {self.send_interval} 秒")
            return True

        except socket.gaierror as e:
            print(f"✗ 地址解析错误: {e}")
            return False
        except ConnectionRefusedError:
            print(f"✗ 连接被拒绝: 请检查服务器是否正在运行")
            return False
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False

    def generate_vehicle_data(self):
        """生成模拟的车辆数据"""
        # 更新模拟状态
        self.speed = max(0, min(120, self.speed + random.uniform(-5, 5)))  # 0-120 km/h
        target_speed = self.speed + random.uniform(-10, 10)

        # 模拟移动 (简化的运动学)
        speed_m_s = self.speed / 3.6  # 转换为 m/s
        self.displacement += speed_m_s * self.send_interval

        # 模拟位置变化（非常简化）
        self.heading = (self.heading + random.uniform(-5, 5)) % 360
        delta_lat = speed_m_s * self.send_interval * 0.00001 * random.uniform(-1, 1)
        delta_lon = speed_m_s * self.send_interval * 0.00001 * random.uniform(-1, 1)
        self.latitude += delta_lat
        self.longitude += delta_lon

        # 获取当前精确时间戳（毫秒级）
        send_timestamp = time.time()

        # 构建数据字典
        data = {
            # === 通信质量评估字段 ===
            "seq": self.sequence_number,  # 序列号
            "send_time": send_timestamp,  # 发送时间戳（Unix时间，秒）

            # === 原有车辆数据字段 ===
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": self.vehicle_id,
            "link_id": f"LINK_{random.randint(1000, 9999)}",
            "offset_m": random.uniform(0, 1000),
            "longitude": self.longitude,
            "latitude": self.latitude,
            "heading_deg": self.heading,
            "vehicle_mode": random.randint(0, 3),
            "battery_soc": random.uniform(20, 100),
            "accel_m_s2": random.uniform(-2, 2),
            "target_speed_kmh": target_speed,
            "actual_speed_kmh": self.speed,
            "total_displacement_m": self.displacement
        }

        self.sequence_number += 1
        return data

    def start(self):
        """开始发送数据"""
        if not self.connect():
            return False

        self.running = True
        print(f"\n开始发送数据... (按 Ctrl+C 停止)\n")
        print(f"{'序列号':>8} | {'速度(km/h)':>12} | {'时间戳':<26}")
        print("-" * 50)

        try:
            while self.running:
                # 生成数据
                data = self.generate_vehicle_data()

                # 转换为JSON并发送
                json_data = json.dumps(data) + "\n"
                self.socket.sendall(json_data.encode('utf-8'))

                # 打印发送信息
                print(f"{data['seq']:>8} | {data['actual_speed_kmh']:>12.2f} | {data['timestamp']}")

                # 等待下一次发送
                time.sleep(self.send_interval)

        except KeyboardInterrupt:
            print("\n\n收到停止信号...")
        except BrokenPipeError:
            print("\n✗ 连接已断开 (服务器关闭)")
        except Exception as e:
            print(f"\n✗ 发送过程中出错: {e}")
        finally:
            self.stop()

    def stop(self):
        """停止发送并关闭连接"""
        print("正在停止发送器...")
        self.running = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except:
                pass
            self.socket = None
        print(f"发送器已停止。总共发送: {self.sequence_number} 条消息")


def main():
    """主程序"""
    print("=" * 60)
    print("  车辆发送端测试程序 v1.0")
    print("=" * 60)
    print()
    print("配置:")
    print("  - 服务器地址: 43.143.207.201")
    print("  - 服务器端口: 8888 (测试环境)")
    print("  - 发送频率: 10 Hz (0.1秒/条)")
    print()

    # 询问用户配置
    use_default = input("使用默认配置? (y/n): ").strip().lower()

    if use_default == 'y':
        relay_address = "43.143.207.201"
        relay_port = 8888
        vehicle_id = "TEST_VEHICLE_001"
        send_interval = 0.1
    else:
        relay_address = input("服务器地址 [43.143.207.201]: ").strip() or "43.143.207.201"
        relay_port = int(input("服务器端口 [8888]: ").strip() or "8888")
        vehicle_id = input("车辆ID [TEST_VEHICLE_001]: ").strip() or "TEST_VEHICLE_001"
        send_hz = float(input("发送频率(Hz) [10]: ").strip() or "10")
        send_interval = 1.0 / send_hz

    print()

    # 创建并启动发送器
    sender = VehicleSenderTest(
        relay_address=relay_address,
        relay_port=relay_port,
        vehicle_id=vehicle_id,
        send_interval=send_interval
    )

    sender.start()
    print("\n程序结束。")


if __name__ == "__main__":
    main()
