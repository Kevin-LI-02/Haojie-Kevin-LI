"""
简易数据接收端
功能：连接到中转服务器，并实时打印接收到的车辆数据。
"""
import socket
import json
import time

SERVER_IP = "43.143.207.201"   # ITRLAB实验室公网ip
SERVER_PORT = 8888

class SimpleReceiver:
    """一个简单的接收器类，封装了所有网络逻辑"""

    def __init__(self, server_ip, server_port):
        self.server_address = (server_ip, server_port)
        self.sock = None
        self.buffer = ""

    def connect(self):
        """连接到中转服务器"""
        print(f"正在尝试连接到服务器: {self.server_address[0]}:{self.server_address[1]} ...")
        try:
            addr_info_list = socket.getaddrinfo(self.server_address[0], self.server_address[1], proto=socket.IPPROTO_TCP)
            family, socktype, proto, _, sockaddr = addr_info_list[0]

            self.sock = socket.socket(family, socktype, proto)
            self.sock.connect(sockaddr)
            self.sock.recv(1024) 
            self.sock.sendall(b"RECEIVER\n")
            print(f"✓ 连接成功！已注册为接收端。")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False

    def receive_loop(self):
        """启动接收循环，持续打印数据"""
        if not self.sock:
            return
        print("\n--- 开始接收车辆数据 (按 Ctrl+C 停止) ---\n")
        try:
            while True:
                data = self.sock.recv(4096)
                if not data:
                    print("\n--- 服务器连接已断开 ---")
                    break
                self.buffer += data.decode('utf-8')

                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    if line:
                        self._process_message(line)

        except KeyboardInterrupt:
            print("\n\n--- 用户中断，程序正在停止 ---")
        except Exception as e:
            print(f"\n✗ 接收过程中发生错误: {e}")
        finally:
            self.close()

    def _process_message(self, message):
        """解析单条JSON消息并格式化打印"""
        try:
            data_dict = json.loads(message)
            
            # 使用 .get() 方法安全地获取数据，即使某些字段不存在也不会报错
            timestamp = data_dict.get('timestamp', 'N/A')
            vehicle_id = data_dict.get('vehicle_id', 'N/A')
            target_speed = data_dict.get('telem_target_speed_kmh', 'N/A')
            actual_speed = data_dict.get('telem_actual_speed_kmh', 'N/A')
            actual_lat = data_dict.get('latitude', 'N/A')
            actual_lon = data_dict.get('longitude', 'N/A')
            
            print(f"[{timestamp}] | 车辆ID: {vehicle_id} | 目标速度: {target_speed} km/h | 实际速度: {actual_speed} km/h | <UNK>: {actual_lat} | <UNK>: {actual_lon}\n")

        except json.JSONDecodeError:
            # 如果收到的不是标准JSON，则直接打印原始消息
            print(f"[原始数据] {message}")
            
    def close(self):
        """关闭socket连接"""
        if self.sock:
            self.sock.close()
            print("--- 连接已关闭 ---")


def main():
    """主函数"""
    print("=" * 60)
    print("                简易车辆数据接收端")
    print("=" * 60)

    receiver = SimpleReceiver(SERVER_IP, SERVER_PORT)
    if receiver.connect():
        receiver.receive_loop()

if __name__ == "__main__":
    main()