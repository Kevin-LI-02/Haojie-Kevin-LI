# ==============================================================================
# 文件名: launch.py
# 版本:   18.1 (最终版 - 精确尺寸 & 纯净启动)
# 更新:
# - [修复] app_main.py 不再自动打开默认浏览器，避免了窗口重复。
# - [核心] create_window 现在使用精确的 width 和 height 参数 (1536x432)，
#   替换了 fullscreen=True，以完美匹配大屏显示区域。
# - [优化] 增加窗口可拖拽区域和最小化/关闭按钮，提升可用性。
# ==============================================================================
import sys
import time
import subprocess
import threading
import webview

# --- 配置 ---
BACKEND_SERVER_SCRIPT = "app_main.py"
DATA_FORWARDER_SCRIPT = ("sim.py" ) #external_simulator.py 换成这个是咱们服务器上读的数据 sim是之前录的数据
SERVER_URL = "http://127.0.0.1:8000"
WINDOW_TITLE = "实时态势图监控系统"

# <<< --- 新增：精确的窗口尺寸配置 --- >>>
WINDOW_WIDTH = 1536
WINDOW_HEIGHT = 432

PYTHON_EXECUTABLE = sys.executable
processes = []


def start_script_in_thread(script_name):
    print(f"🚀 正在后台启动 {script_name}...")
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen([PYTHON_EXECUTABLE, script_name], creationflags=flags)
        processes.append(process)
        print(f"✅ {script_name} 进程已在后台启动 (PID: {process.pid})。")
    except Exception as e:
        print(f"❌ 启动 {script_name} 失败: {e}")


def main():


    backend_thread = threading.Thread(target=start_script_in_thread, args=(BACKEND_SERVER_SCRIPT,), daemon=True)
    backend_thread.start()

    print("⏳ 等待 5 秒，确保后端服务器完全启动...")
    time.sleep(5)

    forwarder_thread = threading.Thread(target=start_script_in_thread, args=(DATA_FORWARDER_SCRIPT,), daemon=True)
    forwarder_thread.start()

    print("\n🚀 正在创建主显示窗口...")
    try:
        # <<< --- 核心修改：使用精确尺寸创建窗口 --- >>>
        webview.create_window(
            WINDOW_TITLE,
            SERVER_URL,
            width=WINDOW_WIDTH,  # 设置精确宽度
            height=WINDOW_HEIGHT,  # 设置精确高度
            resizable=False,  # 禁止调整大小
            frameless=True,  # 保持无边框
            on_top=True  # 保持置顶
        )
        print(f"✅ 主窗口创建成功！尺寸: {WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        webview.start()

    except Exception as e:
        print(f"❌ 创建窗口时发生错误: {e}")

    finally:
        print("\n\n🔴 主窗口已关闭，正在清理所有后台服务...")
        for process in processes:
            if process.poll() is None:
                print(f"   -> 正在终止进程 PID: {process.pid} ...")
                process.terminate()
                process.kill()
        print("✅ 所有服务已关闭。再见！")


if __name__ == "__main__":
    main()