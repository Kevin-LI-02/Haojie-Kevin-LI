#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中转服务器程序 v1.1 - 双通道模式
功能：支持测试和生产两个独立通道，接收车辆端数据，转发给所有连接的接收端

通道配置：
  - 测试环境: 端口 8888 (本地开发测试，多用户可共享)
  - 生产环境: 端口 9999 (实际生产使用，避免互相干扰)

两个通道完全独立，不存在端口阻塞问题。
"""

import socket
import threading
import time
from datetime import datetime


class RelayServer:
    def __init__(self, listen_port=8888, env_name="未命名"):
        """
        初始化中转服务器
        :param listen_port: 监听端口
        :param env_name: 环境名称（如"测试环境"或"生产环境"）
        """
        self.listen_port = listen_port
        self.env_name = env_name
        self.vehicle_clients = []  # 车辆端连接列表
        self.receiver_clients = []  # 接收端连接列表
        self.running = False
        self.lock = threading.Lock()
        
    def start(self):
        """启动服务器"""
        # 创建IPv6 TCP socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # 绑定到所有IPv4地址
            server_socket.bind(('0.0.0.0', self.listen_port))
            server_socket.listen(10)
            self.running = True
            
            print(f"✓ [{self.env_name}] 中转服务器已启动，监听端口: {self.listen_port}")
            print(f"✓ 监听所有IPv4地址 (0.0.0.0)")
            print(f"  等待客户端连接...\n")
            
            # 启动状态显示线程
            status_thread = threading.Thread(target=self.show_status, daemon=True)
            status_thread.start()
            
            while self.running:
                try:
                    client_socket, client_address = server_socket.accept()
                    # 启动客户端处理线程
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    client_thread.start()
                except Exception as e:
                    if self.running:
                        print(f"✗ 接受连接时出错: {e}")
                        
        except Exception as e:
            print(f"✗ 服务器启动失败: {e}")
        finally:
            server_socket.close()
            print("服务器已关闭")
    
    def handle_client(self, client_socket, client_address):
        """
        处理客户端连接
        :param client_socket: 客户端socket
        :param client_address: 客户端地址
        """
        print(f"[{self.env_name}] [{datetime.now().strftime('%H:%M:%S')}] "
              f"新连接来自: [{client_address[0]}]:{client_address[1]}")
        
        # 发送欢迎消息，询问客户端类型
        try:
            client_socket.sendall(b"TYPE:VEHICLE_OR_RECEIVER?\n")
            response = client_socket.recv(1024).decode('utf-8').strip()
            
            if response == "VEHICLE":
                with self.lock:
                    self.vehicle_clients.append(client_socket)
                print(f"  → 注册为车辆端，当前车辆端数量: {len(self.vehicle_clients)}")
                self.handle_vehicle(client_socket, client_address)
                
            elif response == "RECEIVER":
                with self.lock:
                    self.receiver_clients.append(client_socket)
                print(f"  → 注册为接收端，当前接收端数量: {len(self.receiver_clients)}")
                self.keep_receiver_alive(client_socket, client_address)
                
            else:
                print(f"  ✗ 未知客户端类型: {response}")
                client_socket.close()
                
        except Exception as e:
            print(f"  ✗ 处理客户端时出错: {e}")
            self.remove_client(client_socket)
    
    def handle_vehicle(self, client_socket, client_address):
        """
        处理车辆端数据
        :param client_socket: 车辆端socket
        :param client_address: 车辆端地址
        """
        buffer = ""
        
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                buffer += data.decode('utf-8')
                
                # 处理完整的消息（以换行符分隔）
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self.forward_to_receivers(line + '\n')
                        
        except Exception as e:
            print(f"  ✗ 车辆端连接断开 [{client_address[0]}]: {e}")
        finally:
            self.remove_client(client_socket)
    
    def keep_receiver_alive(self, client_socket, client_address):
        """
        保持接收端连接活跃
        :param client_socket: 接收端socket
        :param client_address: 接收端地址
        """
        try:
            while self.running:
                # 接收端可能发送心跳包
                data = client_socket.recv(1024)
                if not data:
                    break
        except Exception as e:
            print(f"  ✗ 接收端连接断开 [{client_address[0]}]: {e}")
        finally:
            self.remove_client(client_socket)
    
    def forward_to_receivers(self, data):
        """
        转发数据到所有接收端
        :param data: 要转发的数据
        """
        with self.lock:
            disconnected = []
            
            for receiver in self.receiver_clients:
                try:
                    receiver.sendall(data.encode('utf-8'))
                except Exception:
                    disconnected.append(receiver)
            
            # 移除断开的接收端
            for receiver in disconnected:
                self.receiver_clients.remove(receiver)
                try:
                    receiver.close()
                except:
                    pass
    
    def remove_client(self, client_socket):
        """移除断开的客户端"""
        with self.lock:
            if client_socket in self.vehicle_clients:
                self.vehicle_clients.remove(client_socket)
                print(f"  车辆端已断开，剩余: {len(self.vehicle_clients)}")
            elif client_socket in self.receiver_clients:
                self.receiver_clients.remove(client_socket)
                print(f"  接收端已断开，剩余: {len(self.receiver_clients)}")
        
        try:
            client_socket.close()
        except:
            pass
    
    def show_status(self):
        """定期显示服务器状态"""
        while self.running:
            time.sleep(10)
            with self.lock:
                print(f"\n[{self.env_name}状态] 车辆端: {len(self.vehicle_clients)}, "
                      f"接收端: {len(self.receiver_clients)}\n")
    
    def stop(self):
        """停止服务器"""
        self.running = False
        with self.lock:
            for client in self.vehicle_clients + self.receiver_clients:
                try:
                    client.close()
                except:
                    pass


def main():
    print("=" * 70)
    print("IPv4 中转服务器 - 双通道模式（测试+生产）")
    print("=" * 70)
    print()

    # 创建两个独立的服务器实例
    test_server = RelayServer(listen_port=8888, env_name="测试环境")
    prod_server = RelayServer(listen_port=9999, env_name="生产环境")

    # 在独立线程中启动两个服务器
    test_thread = threading.Thread(target=test_server.start, daemon=False)
    prod_thread = threading.Thread(target=prod_server.start, daemon=False)

    test_thread.start()
    prod_thread.start()

    try:
        # 保持主线程活跃
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n正在停止所有服务器...")
        test_server.stop()
        prod_server.stop()
        test_thread.join(timeout=2)
        prod_thread.join(timeout=2)
        print("所有服务器已停止。")


if __name__ == "__main__":
    main()

