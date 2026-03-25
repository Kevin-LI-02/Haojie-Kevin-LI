#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试脚本 - 用于测试通信质量监测功能
该脚本演示如何：
1. 启动中转服务器
2. 启动测试发送端
3. 启动接收端并监测通信质量
"""

import sys
import time
import subprocess
import threading
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def run_relay_server():
    """启动中转服务器"""
    print_header("启动中转服务器 - relay_ipv4.py")
    print("中转服务器正在监听 0.0.0.0:8888 和 0.0.0.0:9999...")
    print("请在新的终端窗口中运行:")
    print(f"\n  python \"{PROJECT_ROOT / 'relay_ipv4.py'}\"")
    print("\n")


def run_vehicle_sender():
    """启动车辆发送端"""
    print_header("启动车辆发送端 - vehicle_sender_test.py")
    print("车辆发送端正在发送测试数据...")
    print("请在新的终端窗口中运行:")
    print(f"\n  python \"{PROJECT_ROOT / 'vehicle_sender_test.py'}\"")
    print("\n选择默认配置 (y)")
    print("\n")


def run_receiver_quality_monitoring():
    """启动接收端（带质量监测）"""
    print_header("启动接收端 - data_receiver_interface.py")
    print("接收端将连接到服务器并监测通信质量...")
    print("请在新的终端窗口中运行:")
    print(f"\n  python \"{PROJECT_ROOT / 'data_receiver_interface.py'}\"")
    print("\n选择选项 3 (质量监测模式)")
    print("\n")


def print_instructions():
    """打印详细的运行说明"""
    print("\n" + "=" * 70)
    print("  通信质量监测系统 - 完整测试指南")
    print("=" * 70)

    print("""
【系统架构】
  ┌──────────────┐
  │ Vehicle Sender (车辆端)
  └──────────────┘
           │
           ↓
  ┌──────────────────┐
  │ Relay Server     │ (中转服务器)
  │ Port 8888, 9999  │
  └──────────────────┘
           │
           ↓
  ┌──────────────┐
  │ Data Receiver (接收端)
  │ + 质量监测    │
  └──────────────┘

【通信质量指标】
  • 丢包率 (Packet Loss Rate): 丢失包数 / 预期包数
  • 时延 (Latency): 端到端传输时间
  • 抖动 (Jitter): 时延的标准差
  • 吞吐量 (Throughput): 每秒接收的包数

【测试步骤】

步骤 1: 启动中转服务器
  在第一个终端运行:
  python relay_ipv4.py

  预期输出:
    ✓ [测试环境] 中转服务器已启动，监听端口: 8888
    ✓ [生产环境] 中转服务器已启动，监听端口: 9999

步骤 2: 启动车辆发送端（在第二个终端运行）
  python vehicle_sender_test.py

  选择: y (使用默认配置)

  预期输出:
    ✓ 已连接到中转服务器: 43.143.207.201:8888
    ✓ 车辆ID: TEST_VEHICLE_001
    ✓ 发送间隔: 0.1 秒
    [数据发送列表...]

步骤 3: 启动接收端（在第三个终端运行）
  python data_receiver_interface.py

  选择: 3 (质量监测模式)

  预期输出:
    ✓ [测试-质量监测] 已连接到中转服务器: 43.143.207.201:8888
    [实时接收的消息...]

    每5秒显示一次统计信息:
    ======================================================================
      通信质量统计报告 - 2025-12-04 12:34:56
    ======================================================================

    【总体通信质量】
      运行时间:     15.3 秒
      接收包数:     153
      预期包数:     153
      丢包数:       0
      丢包率:       0.00%
      吞吐量:       10.00 包/秒

    【时延统计】
      平均时延:     45.32 ms
      最小时延:     42.10 ms
      最大时延:     48.50 ms
      抖动 (标准差): 2.15 ms

    【各车辆通信质量】
      车辆ID              | 接收    | 丢包   | 丢包率    | 平均时延
      ────────────────────────────────────────────────────────────
      TEST_VEHICLE_001    | 153     | 0      | 0.00%    | 45.32 ms
    ======================================================================

【关键指标说明】

1. 丢包率 (Packet Loss Rate)
   • 0% 是最好的情况
   • > 5% 表示网络质量较差
   • > 10% 表示网络问题严重

2. 平均时延 (Average Latency)
   • 一般车辆应用: < 200ms 可接受
   • 实时控制应用: < 50ms 为好
   • 当前测试: ~45ms 很好

3. 抖动 (Jitter)
   • 越小越好，表示网络稳定
   • < 5ms 为优秀
   • > 20ms 可能影响实时应用

【监控多个发送端】

如果要测试多个车辆，可以启动多个发送端:

  # 终端 2a: 车辆 1
  python vehicle_sender_test.py
  选择: n
  - 服务器地址: 43.143.207.201
  - 端口: 8888
  - 车辆ID: VEHICLE_001
  - 发送频率: 10

  # 终端 2b: 车辆 2
  python vehicle_sender_test.py
  选择: n
  - 服务器地址: 43.143.207.201
  - 端口: 8888
  - 车辆ID: VEHICLE_002
  - 发送频率: 10

接收端会自动统计每个车辆的通信质量。

【测试异常情况】

可以测试网络问题（模拟）：
1. 杀死某个发送端 - 观察丢包率变化
2. 修改发送频率 - 观察吞吐量变化
3. 多个接收端同时连接 - 观察中转服务器转发性能

【在代码中使用质量监测】

from data_receiver_interface import DataReceiver

def my_handler(data):
    # 自定义数据处理
    pass

# 启用质量监测
receiver = DataReceiver(
    relay_ipv6="43.143.207.201",
    relay_port=8888,
    mode="测试",
    enable_quality_monitor=True  # 启用质量监测
)

receiver.set_callback(my_handler)
receiver.start()

# 接收端会自动进行质量监测和统计

【注意事项】

1. 确保中转服务器正在运行
2. 使用 Ctrl+C 优雅地停止程序
3. 停止时会显示最终的统计信息
4. 所有时间戳使用 Unix 时间（秒）
5. 时延以毫秒（ms）为单位

""")

    print("=" * 70 + "\n")


def main():
    """主程序"""
    print_header("通信质量监测系统 - 集成测试")

    print("本测试演示如何使用通信质量监测功能。\n")
    print("请选择:")
    print("  1 - 显示完整说明（推荐）")
    print("  2 - 显示快速开始指南")
    print("  3 - 直接开始测试")

    choice = input("\n请输入选择 (1, 2 或 3): ").strip()

    if choice == "1":
        print_instructions()
    elif choice == "2":
        print_header("快速开始")
        print("打开三个终端窗口，分别运行:\n")
        run_relay_server()
        run_vehicle_sender()
        run_receiver_quality_monitoring()
        print("=" * 70)
        print("  所有组件运行后，接收端会定期显示通信质量统计。")
        print("=" * 70 + "\n")
    elif choice == "3":
        print_header("开始测试")
        run_relay_server()
        run_vehicle_sender()
        run_receiver_quality_monitoring()
    else:
        print("无效选择。")


if __name__ == "__main__":
    main()
