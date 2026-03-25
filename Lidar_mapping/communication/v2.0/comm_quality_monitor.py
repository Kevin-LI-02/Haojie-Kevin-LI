#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通信质量监测模块 v1.0
功能：计算和统计通信质量指标，包括丢包率、时延、抖动等
"""

import time
import threading
from collections import deque
from datetime import datetime


class CommQualityMonitor:
    """通信质量监测器"""

    def __init__(self, window_size=100, display_interval=5.0):
        """
        初始化通信质量监测器
        :param window_size: 滑动窗口大小（用于计算统计值）
        :param display_interval: 统计信息显示间隔（秒）
        """
        self.window_size = window_size
        self.display_interval = display_interval

        # 全局统计
        self.total_received = 0  # 总接收包数
        self.total_lost = 0  # 总丢包数
        self.total_expected = 0  # 预期总包数
        self.last_seq = None  # 上一个序列号
        self.first_seq = None  # 第一个序列号

        # 时延统计（滑动窗口）
        self.latency_window = deque(maxlen=window_size)  # 存储最近的时延值
        self.min_latency = float('inf')
        self.max_latency = 0

        # 每个车辆的独立统计
        self.vehicle_stats = {}  # key: vehicle_id, value: VehicleQualityStats

        # 线程锁
        self.lock = threading.Lock()

        # 统计显示相关
        self.last_display_time = time.time()
        self.start_time = time.time()

    def process_message(self, data_dict):
        """
        处理接收到的消息，更新统计信息
        :param data_dict: 包含车辆数据的字典
        """
        receive_time = time.time()

        with self.lock:
            # 提取通信质量字段
            seq = data_dict.get('seq')
            send_time = data_dict.get('send_time')
            vehicle_id = data_dict.get('vehicle_id', 'UNKNOWN')

            # 如果消息不包含质量字段，跳过统计
            if seq is None or send_time is None:
                return

            # === 全局统计 ===
            self.total_received += 1

            # 计算时延（毫秒）
            latency_ms = (receive_time - send_time) * 1000
            self.latency_window.append(latency_ms)
            self.min_latency = min(self.min_latency, latency_ms)
            self.max_latency = max(self.max_latency, latency_ms)

            # 丢包检测
            if self.first_seq is None:
                self.first_seq = seq
                self.last_seq = seq
            else:
                expected_seq = self.last_seq + 1
                if seq > expected_seq:
                    # 检测到丢包
                    lost_count = seq - expected_seq
                    self.total_lost += lost_count
                elif seq < expected_seq:
                    # 乱序或重复包（这里简化处理，不计入统计）
                    pass

                self.last_seq = max(seq, self.last_seq)

            # 计算预期总包数
            if self.first_seq is not None and self.last_seq is not None:
                self.total_expected = self.last_seq - self.first_seq + 1

            # === 单车辆统计 ===
            if vehicle_id not in self.vehicle_stats:
                self.vehicle_stats[vehicle_id] = VehicleQualityStats(vehicle_id)

            self.vehicle_stats[vehicle_id].update(seq, send_time, receive_time)

    def get_statistics(self):
        """
        获取当前统计信息
        :return: 包含所有统计指标的字典
        """
        with self.lock:
            # 计算平均时延
            avg_latency = sum(self.latency_window) / len(self.latency_window) if self.latency_window else 0

            # 计算抖动（时延标准差）
            if len(self.latency_window) > 1:
                mean = avg_latency
                variance = sum((x - mean) ** 2 for x in self.latency_window) / len(self.latency_window)
                jitter = variance ** 0.5
            else:
                jitter = 0

            # 计算丢包率
            packet_loss_rate = (self.total_lost / self.total_expected * 100) if self.total_expected > 0 else 0

            # 计算吞吐量（包/秒）
            elapsed_time = time.time() - self.start_time
            throughput = self.total_received / elapsed_time if elapsed_time > 0 else 0

            # 获取车辆统计
            vehicle_stats_list = []
            for vehicle_id, stats in self.vehicle_stats.items():
                vehicle_stats_list.append(stats.get_statistics())

            return {
                'total_received': self.total_received,
                'total_expected': self.total_expected,
                'total_lost': self.total_lost,
                'packet_loss_rate': packet_loss_rate,
                'avg_latency_ms': avg_latency,
                'min_latency_ms': self.min_latency if self.min_latency != float('inf') else 0,
                'max_latency_ms': self.max_latency,
                'jitter_ms': jitter,
                'throughput_pps': throughput,
                'elapsed_time_s': elapsed_time,
                'vehicle_stats': vehicle_stats_list
            }

    def print_statistics(self):
        """打印统计信息（格式化输出）"""
        stats = self.get_statistics()

        print("\n" + "=" * 70)
        print(f"  通信质量统计报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # === 总体统计 ===
        print("\n【总体通信质量】")
        print(f"  运行时间:     {stats['elapsed_time_s']:.1f} 秒")
        print(f"  接收包数:     {stats['total_received']}")
        print(f"  预期包数:     {stats['total_expected']}")
        print(f"  丢包数:       {stats['total_lost']}")
        print(f"  丢包率:       {stats['packet_loss_rate']:.2f}%")
        print(f"  吞吐量:       {stats['throughput_pps']:.2f} 包/秒")

        print(f"\n【时延统计】")
        print(f"  平均时延:     {stats['avg_latency_ms']:.2f} ms")
        print(f"  最小时延:     {stats['min_latency_ms']:.2f} ms")
        print(f"  最大时延:     {stats['max_latency_ms']:.2f} ms")
        print(f"  抖动 (标准差): {stats['jitter_ms']:.2f} ms")

        # === 各车辆统计 ===
        if stats['vehicle_stats']:
            print(f"\n【各车辆通信质量】")
            print(f"  {'车辆ID':<20} | {'接收':<8} | {'丢包':<8} | {'丢包率':<10} | {'平均时延':<12}")
            print("  " + "-" * 68)

            for v_stats in stats['vehicle_stats']:
                print(f"  {v_stats['vehicle_id']:<20} | "
                      f"{v_stats['received']:<8} | "
                      f"{v_stats['lost']:<8} | "
                      f"{v_stats['loss_rate']:<9.2f}% | "
                      f"{v_stats['avg_latency_ms']:<11.2f} ms")

        print("=" * 70 + "\n")

    def should_display(self):
        """判断是否应该显示统计信息"""
        current_time = time.time()
        if current_time - self.last_display_time >= self.display_interval:
            self.last_display_time = current_time
            return True
        return False


class VehicleQualityStats:
    """单个车辆的通信质量统计"""

    def __init__(self, vehicle_id):
        self.vehicle_id = vehicle_id
        self.received = 0
        self.lost = 0
        self.expected = 0
        self.last_seq = None
        self.first_seq = None
        self.latency_sum = 0
        self.latency_count = 0

    def update(self, seq, send_time, receive_time):
        """更新统计信息"""
        self.received += 1

        # 计算时延
        latency_ms = (receive_time - send_time) * 1000
        self.latency_sum += latency_ms
        self.latency_count += 1

        # 丢包检测
        if self.first_seq is None:
            self.first_seq = seq
            self.last_seq = seq
        else:
            expected_seq = self.last_seq + 1
            if seq > expected_seq:
                lost_count = seq - expected_seq
                self.lost += lost_count

            self.last_seq = max(seq, self.last_seq)

        # 计算预期包数
        if self.first_seq is not None and self.last_seq is not None:
            self.expected = self.last_seq - self.first_seq + 1

    def get_statistics(self):
        """获取统计信息"""
        loss_rate = (self.lost / self.expected * 100) if self.expected > 0 else 0
        avg_latency = (self.latency_sum / self.latency_count) if self.latency_count > 0 else 0

        return {
            'vehicle_id': self.vehicle_id,
            'received': self.received,
            'expected': self.expected,
            'lost': self.lost,
            'loss_rate': loss_rate,
            'avg_latency_ms': avg_latency
        }


# ============ 测试代码 ============

if __name__ == "__main__":
    """测试通信质量监测器"""
    monitor = CommQualityMonitor(window_size=100, display_interval=2)

    # 模拟接收消息
    print("开始模拟消息接收...\n")

    for i in range(200):
        # 模拟正常消息
        data = {
            'seq': i,
            'send_time': time.time() - 0.05,  # 模拟50ms时延
            'vehicle_id': f"VEHICLE_{i % 3 + 1}"  # 3辆车
        }

        # 模拟丢包（每20个包丢1个）
        if i % 20 == 0 and i > 0:
            continue

        monitor.process_message(data)

        # 定期显示统计
        if monitor.should_display():
            monitor.print_statistics()

        time.sleep(0.01)

    # 最终统计
    print("\n最终统计:")
    monitor.print_statistics()
