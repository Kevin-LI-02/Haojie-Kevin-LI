# ==============================================================================
# 文件名: start_all.py
# 描述:   一键启动脚本。
#         该脚本会并行启动后端服务器 (app_main.py) 和数据转发器
#         (external_simulator.py)，并管理它们的生命周期。
#
# 使用方法:
# 1. 打开一个终端。
# 2. 运行命令: python start.py
# 3. 两个服务将在后台启动。
# 4. 如需停止所有服务，请直接关闭此终端窗口 (按 Ctrl+C)。
# ==============================================================================
import sys
import time
import subprocess
import os

# --- 配置 ---
# 定义要启动的脚本文件名
BACKEND_SERVER_SCRIPT = "app_main.py"
DATA_FORWARDER_SCRIPT = "external_simulator.py"

# 获取当前Python解释器的路径，确保子进程使用与主进程相同的环境
PYTHON_EXECUTABLE = sys.executable


def print_header(title):
    """打印带边框的标题"""
    width = 60
    print("\n" + "=" * width)
    print(f"{title:^{width}}")
    print("=" * width)


def check_script_exists(script_name):
    """检查脚本文件是否存在"""
    if not os.path.exists(script_name):
        print(f"❌ 错误: 脚本 '{script_name}' 未找到。请确保此脚本与 start_all.py 在同一目录下。")
        return False
    return True


def main():
    print_header("多服务一键启动器")

    # 检查所需脚本是否存在
    if not check_script_exists(BACKEND_SERVER_SCRIPT) or not check_script_exists(DATA_FORWARDER_SCRIPT):
        sys.exit(1)  # 退出程序

    processes = []  # 用于存储所有子进程的列表
    try:
        # --- 步骤 1: 启动后端服务器 ---
        print(f"🚀 正在启动后端服务器 ({BACKEND_SERVER_SCRIPT})...")
        # 使用 Popen 启动子进程，它不会阻塞
        # stdout=subprocess.PIPE 和 stderr=subprocess.STDOUT 会捕获输出，如果需要可以读取
        # 如果希望输出直接打印到当前终端，可以移除 stdout 和 stderr 参数
        backend_process = subprocess.Popen(
            [PYTHON_EXECUTABLE, BACKEND_SERVER_SCRIPT],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        processes.append(backend_process)
        print(f"✅ 后端服务器进程已启动 (PID: {backend_process.pid})。")

        # --- 步骤 2: 等待服务器就绪 ---
        print("\n⏳ 等待 3 秒，确保后端服务器完全启动...")
        time.sleep(3)

        # --- 步骤 3: 启动数据转发器 ---
        print(f"\n🚀 正在启动数据转发器 ({DATA_FORWARDER_SCRIPT})...")
        forwarder_process = subprocess.Popen(
            [PYTHON_EXECUTABLE, DATA_FORWARDER_SCRIPT],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        processes.append(forwarder_process)
        print(f"✅ 数据转发器进程已启动 (PID: {forwarder_process.pid})。")

        print_header("所有服务已成功启动！")
        print("ℹ️ 您现在可以打开浏览器查看 http://127.0.0.1:8000")
        print("🔴 如需停止所有服务，请关闭此启动器窗口 (或按 Ctrl+C)。")

        # 主进程在此等待，直到用户中断
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🔴 检测到用户中断 (Ctrl+C)...")

    except Exception as e:
        print(f"\n\n❌ 启动过程中发生意外错误: {e}")

    finally:
        # --- 步骤 4: 清理和终止所有子进程 ---
        print_header("正在关闭所有服务...")
        for process in processes:
            if process.poll() is None:  # 检查进程是否还在运行
                print(f"   -> 正在终止进程 PID: {process.pid} ...")
                process.terminate()  # 发送终止信号
                try:
                    process.wait(timeout=5)  # 等待最多5秒
                    print(f"   ✓ 进程 {process.pid} 已成功关闭。")
                except subprocess.TimeoutExpired:
                    print(f"   ⚠️ 进程 {process.pid} 未能在5秒内响应，强制终止...")
                    process.kill()  # 强制杀死进程
                    print(f"   ✓ 进程 {process.pid} 已被强制关闭。")
        print("\n所有服务已关闭。再见！")


if __name__ == "__main__":
    main()