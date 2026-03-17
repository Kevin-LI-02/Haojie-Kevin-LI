# turnout.py

import sys
import os
import cv2
import csv
import re
import datetime
import time
import requests
import smtplib
import numpy as np
import winsound

# 导入实时推送模块
try:
    from realtime_push import push_turnout_data
except ImportError:
    push_turnout_data = None
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from PyQt5 import QtCore, QtGui,QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QPushButton, QFileDialog, QWidget, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QScrollBar, QDialog, QStatusBar, QTabWidget, QFormLayout,
    QLineEdit, QComboBox, QListWidget, QDialogButtonBox, QCheckBox, QAbstractItemView
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QObject, QEvent
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
from paddleocr import PaddleOCR
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from collections import defaultdict
from performance_monitor import PerformanceMonitor

# OCR 初始化 - 明确启用GPU加速
ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=True)

# OCR 线程类
class OCRThread(QtCore.QThread):
    result_signal = pyqtSignal(list, object)  # 用于传递OCR结果的信号

    def __init__(self, ocr_instance, frame, regions_list):
        super().__init__()
        self.ocr_instance = ocr_instance
        self.frame = frame
        self.regions_list = regions_list

    def run(self):
        try:
            ocr_results = self.process_ocr(self.frame, self.regions_list)
            self.result_signal.emit(ocr_results, self.frame)  # 将结果通过信号传递
        except Exception as e:
            print(f"OCR线程错误: {e}")

    def process_ocr(self, frame, regions_list):
        ocr_results = []
        for regions in regions_list:
            result = self.ocr_instance.ocr(frame, cls=True)
            ocr_results.append(result)
        return ocr_results

class TurnoutIntegration(QObject):
    update_video_signal = pyqtSignal(QtGui.QImage)  # 用于更新视频显示
    update_ocr_signal = pyqtSignal(QtGui.QImage)  # 用于更新 OCR 结果显示

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.auto_scroll_enabled = True  # 添加或确保自动滚动标志默认为 True
        self.ui.frame_20.setStyleSheet("border-radius:0px; background-color:#2f5597;")
        self.ui.frame_21.setStyleSheet("border-radius:0px; background-color:#2f5597;")

        # 加载道岔编号配置文件
        self.turnout_config_file = "turnout_ids_setting.csv"
        self.station_turnout_map = self.load_turnout_config()

        # 默认使用第一个车站的道岔编号
        if self.station_turnout_map:
            default_station = next(iter(self.station_turnout_map.keys()))
            self.turnout_ids_setting = self.get_turnout_ids_for_station(default_station)
            self.turnout_keywords = set([tid.strip() for tid in self.turnout_ids_setting.split(',')])
        else:
            # 如果配置文件为空，使用默认UNI数据
            self.turnout_ids_setting = "5903,5902,5911,5912"
            self.turnout_keywords = set([tid.strip() for tid in self.turnout_ids_setting.split(',')])

        self.settings = self.load_settings_from_csv("default account.csv")
        if not self.settings:
            # 如果加载失败，可以给出提示或者使用默认值
            # print("Warning: Could not load settings from 'default account.csv'. Using default values.")
            # 在这里可以设置一些备用/默认的参数
            self.settings = {
                "WeChat Webhook URL": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=b05a8fb5-5469-49b1-ad91-7fbc0738eb26",
                "Receiver Email": "eal.bjtu@gmail.com",
                "Smtp server": "smtp.163.com",
                "Smtp port": "465",
                "Sender email": "lihaojie0044@163.com",
                "Sender password": "AQri6kUXQ4tK9nNC"
            }

        # 连接车站选择变化信号
        self.ui.comboBox_28.currentTextChanged.connect(self.on_station_changed)

        self.conversion_time_diffs = []
        self.last_conversion_time = None
        self.previous_status = None
        self.csv_writer = None
        self.csv_file = None
        self.is_running = False
        self.previous_colors = {}
        self.alert_keywords = {"stopping", "overrun", "alarm", "stepped", "missed", "point", "limit"}
        # self.turnout_keywords = set([tid.strip() for tid in self.turnout_ids_setting.split(',')])
        self.priority_keywords = {"Critical", "emergency", "failure", "shutdown"}
        self.previous_text_colors = {}
        self.previous_rectangle_colors = {}
        self.manual_partitions = []
        self.video_started = False
        self.cap = None
        self.frame_skip = 10  # GPU优化：10帧跳帧，约0.3-0.4秒检测一次（平衡实时性和性能）
        self.frame_count = 0
        self.plot_data = defaultdict(lambda: {'timestamps': [], 'durations': []})
        self.turnout_status = {}
        self.performance_monitor = PerformanceMonitor(
            module_name="Turnout Detection",
            log_dir=os.path.join("performance_logs", "turnout"),
        )

        # 初始化chart放在这里，因为UI初始化在main.py中做
        self.initChart()

        # 连接按钮信号到槽函数 (page_5 buttons)
        self.ui.pushButton_32.clicked.connect(self.start_detection) # Start OCR Detection
        self.ui.pushButton_33.clicked.connect(self.resetDetectionRegion) # Reset/Adjust Detection Region
        self.ui.pushButton_34.clicked.connect(self.cancelLastSelection) # Cancel Last Selection
        self.ui.pushButton_35.clicked.connect(self.stop_detection) # Stop Detection
        self.ui.pushButton_36.clicked.connect(self.send_notification) # Send Notification
        self.ui.pushButton_37.clicked.connect(self.play_sound_alert) # Send Email Notification
        self.ui.pushButton_38.clicked.connect(self.send_email) # Sound Alert

        # Connect Settings Page Buttons
        self.ui.pushButton_30.clicked.connect(self.set_turnout_ids)
        self.ui.pushButton_53.clicked.connect(self.set_wechat_webhook_url)
        self.ui.pushButton_54.clicked.connect(self.set_receiver_email)
        self.ui.pushButton_55.clicked.connect(self.set_smtp_settings)
        # self.ui.pushButton_56.clicked.connect(self.set_abnormal_dwell_time) # Dummy function for now


        # 连接 page_8 buttons (chart operations) - These need to be connected to matplotlib navigation toolbar functions if directly controlling toolbar buttons is not feasible
        # For now, leaving these as placeholders - actual implementation depends on how toolbar interaction is desired.
        # In a real scenario, you might need to customize the NavigationToolbar or implement these functionalities directly.
        self.ui.pushButton_3.clicked.connect(self.reset_original_view) # Dummy function - needs matplotlib integration
        self.ui.pushButton_25.clicked.connect(self.back_to_previous_view) # Dummy function - needs matplotlib integration
        self.ui.pushButton_24.clicked.connect(self.forward_to_next_view) # Dummy function - needs matplotlib integration
        self.ui.pushButton_13.clicked.connect(self.pan_chart) # Dummy function - needs matplotlib integration
        self.ui.pushButton_6.clicked.connect(self.zoom_to_rectangle) # Dummy function - needs matplotlib integration
        self.ui.pushButton_5.clicked.connect(self.configures_subplots) # Dummy function - needs matplotlib integration
        self.ui.pushButton_2.clicked.connect(self.edit_axis_curve_image_parameters) # Dummy function - needs matplotlib integration
        self.ui.pushButton_26.clicked.connect(self.save_figure) # Dummy function - needs matplotlib integration


        # 初始化视频显示区域和OCR结果显示区域 (assuming frame_20 and frame_21 are meant for video and OCR respectively)
        self.videoLabel = QLabel()
        self.videoLabel.setScaledContents(True)
        layout20 = QVBoxLayout(self.ui.frame_20) # Use frame_20 from UI
        layout20.setContentsMargins(0, 0, 0, 0)
        layout20.addWidget(self.videoLabel)

        self.ocrLabel = QLabel()
        self.ocrLabel.setScaledContents(True)
        layout21 = QVBoxLayout(self.ui.frame_21) # Use frame_21 from UI
        layout21.setContentsMargins(0, 0, 0, 0)
        layout21.addWidget(self.ocrLabel)

        # 初始化表格 (assuming tableWidget_3 is the correct table)
        self.turnoutTable = self.ui.tableWidget_3 # Use tableWidget_3 from UI
        self.turnoutTable.setRowCount(0)
        self.turnoutTable.setColumnCount(5)
        self.turnoutTable.setHorizontalHeaderLabels(['Turnout ID', 'Date/Time', 'Status', 'Throw Time', 'Text'])
        self.turnoutTable.setColumnWidth(1, 260)
        self.turnoutTable.setColumnWidth(2, 260)
        self.turnoutTable.setColumnWidth(3, 500)
        self.turnoutTable.setColumnWidth(4, 800)
        self.turnoutTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.turnoutTable.setSelectionMode(QAbstractItemView.SingleSelection)

        # 鼠标事件处理 -  Event filter needs to be installed in main.py on the video frame (frame_20)
        # Mouse tracking is also set in main.py
        self.toolbar.locales = 'en_US.UTF-8'  # 强制使用英文格式
        self.toolbar.coord_format = lambda x, y: f"x={x:.3f}  y={y:.3f}"  # 保留3位小数

        # 新增鼠标跟踪相关属性
        self.is_selecting = False
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.manual_partitions = []

        # 安装事件过滤器
        self.videoLabel.installEventFilter(self)

        def _init_status_bar(self):
            """手动为 QDialog 添加状态栏"""
            self.status_bar = QStatusBar()

            # 获取对话框的布局
            dialog_layout = self.ui.layout()
            if not dialog_layout:
                # 如果对话框没有布局，创建并设置新布局
                dialog_layout = QVBoxLayout()
                self.ui.setLayout(dialog_layout)

            # 添加状态栏到底部
            dialog_layout.addWidget(self.status_bar)

            # 创建坐标标签
            self.coord_label = QLabel("x=?, y=?")
            self.status_bar.addPermanentWidget(self.coord_label)

        def on_mouse_move(event):
            if event.inaxes:
                # 将 x 轴数值转换为日期时间格式
                import matplotlib.dates as mdates
                time_str = mdates.num2date(event.xdata).strftime('%H:%M:%S')
                # 更新坐标显示
                self.coord_label.setText(f"x={time_str}, y={event.ydata:.3f}")

        self.canvas.mpl_connect('motion_notify_event', on_mouse_move)

    def initChart(self):
        # 创建Matplotlib图形和轴
        self.figure = Figure(figsize=(8, 4)) # Set figure facecolor to match background
        self.canvas = FigureCanvas(self.figure)
        # self.canvas.setStyleSheet("background-color: #2f5597;") # Set canvas background to match background
        self.ax = self.figure.add_subplot(111) # Set axes facecolor to match background
        self.ax.set_xlabel('Time', color='black') # Set axis labels to white
        self.ax.set_ylabel('Duration (s)', color='black') # Set axis labels to white
        self.ax.set_title('Throw Time Trend', color='black') # Set title to white
        self.ax.tick_params(axis='x', colors='black')    # 设置x轴刻度颜色为白色
        self.ax.tick_params(axis='y', colors='black')    # 设置y轴刻度颜色为白色
        self.ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        self.figure.autofmt_xdate()
        self.toolbar = NavigationToolbar(self.canvas, self.ui.frame_29)

        layout29 = QVBoxLayout(self.ui.frame_29)
        layout29.setContentsMargins(0, 0, 0, 0)
        layout29.addWidget(self.toolbar)
        layout29.addWidget(self.canvas)

        # Add this to properly handle coordinate display
        def on_mouse_move(event):
            if event.inaxes:
                # 将 x 轴数值转换为日期时间格式
                import matplotlib.dates as mdates
                time_str = mdates.num2date(event.xdata).strftime('%H:%M:%S')
                # 更新坐标显示
                self.coord_label.setText(f"x={time_str}, y={event.ydata:.3f}")

        # Connect the mouse movement event
        self.canvas.mpl_connect('motion_notify_event', on_mouse_move)

    def load_settings_from_csv(self, filename):
        """
        从CSV文件中加载配置参数。
        """
        settings = {}
        try:
            with open(filename, mode='r', encoding='utf-8') as infile:
                reader = csv.reader(infile)
                next(reader)  # 跳过表头
                for row in reader:
                    if len(row) >= 2:
                        parameter = row[0].strip()
                        content = row[1].strip()
                        settings[parameter] = content
            # print(f"Settings loaded successfully from {filename}.")
            return settings
        except FileNotFoundError:
            # print(f"Error: The file {filename} was not found.")
            return None
        except Exception as e:
            # print(f"An error occurred while reading {filename}: {e}")
            return None

    def update_plot_data(self, turnout_id, timestamp, duration):
        """更新绘图数据"""
        if turnout_id not in self.plot_data:
            self.plot_data[turnout_id] = {'timestamps': [], 'durations': []}

        if isinstance(timestamp, str):
            timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

        self.plot_data[turnout_id]['timestamps'].append(timestamp)
        self.plot_data[turnout_id]['durations'].append(duration)
        self.update_chart()

    def load_turnout_config(self):
        """从CSV文件加载车站道岔配置"""
        station_turnout_map = {}
        try:
            with open(self.turnout_config_file, mode='r', encoding='utf-8-sig') as file:  # 使用utf-8-sig处理可能的BOM
                reader = csv.reader(file)
                headers = next(reader)  # 读取标题行

                # 检查CSV格式是否正确
                if len(headers) < 2 or headers[0].lower() != "station" or headers[1].lower() != "turnout":
                    print("CSV文件格式不正确，需要包含'station'和'turnout'列头")
                    return station_turnout_map

                # 读取车站名称和对应的道岔编号
                for row in reader:
                    if len(row) < 2:
                        continue
                    station = row[0].strip()
                    turnout_ids = row[1].strip()
                    if station and turnout_ids:
                        station_turnout_map[station] = turnout_ids

            print(f"成功加载车站道岔配置: {station_turnout_map}")

        except FileNotFoundError:
            print(f"未找到配置文件: {self.turnout_config_file}")
        except Exception as e:
            print(f"加载配置文件出错: {str(e)}")

        return station_turnout_map

    def on_station_changed(self, station):
        """当车站选择变化时更新道岔编号"""
        if not station:
            return

        self.turnout_ids_setting = self.get_turnout_ids_for_station(station)
        if not self.turnout_ids_setting:
            print(f"未找到车站 {station} 的道岔配置")
            return

        self.turnout_keywords = set([tid.strip() for tid in self.turnout_ids_setting.split(',')])
        print(f"已切换到车站 {station}，道岔编号: {self.turnout_ids_setting}")

    def get_turnout_ids_for_station(self, station):
        """获取指定车站的道岔编号"""
        return self.station_turnout_map.get(station, "")

    def update_chart(self):
        """更新折线图"""
        self.ax.clear()

        self.ax.tick_params(axis='x', colors='black', labelsize=9)  # X轴刻度
        self.ax.tick_params(axis='y', colors='black', labelsize=9)  # Y轴刻度
        self.ax.xaxis.label.set_color('black')  # X轴标签
        self.ax.yaxis.label.set_color('black')  # Y轴标签
        self.ax.title.set_color('black')  # 图表标题

        # self.ax.set_facecolor('#2f5597') # Ensure axes background is set on each update
        if not self.plot_data:
            return

        # 找出所有时间戳的范围
        all_timestamps = []
        for data in self.plot_data.values():
            all_timestamps.extend(data['timestamps'])

        if all_timestamps:
            min_time = min(all_timestamps)
            max_time = max(all_timestamps)

            # 计算合适的时间间隔
            time_range = max_time - min_time
            seconds = time_range.total_seconds()

            # 根据时间范围动态调整格式和间隔
            if seconds < 60:  # 少于1分钟
                date_format = DateFormatter('%H:%M:%S')
                # 设置大约5-7个刻度
                self.ax.xaxis.set_major_locator(plt.MaxNLocator(5))
            elif seconds < 3600:  # 少于1小时
                date_format = DateFormatter('%H:%M:%S')
                # 设置大约5-7个刻度
                self.ax.xaxis.set_major_locator(plt.MaxNLocator(6))
            else:  # 大于1小时
                date_format = DateFormatter('%H:%M:%S')
                # 设置大约5-7个刻度
                self.ax.xaxis.set_major_locator(plt.MaxNLocator(7))

            self.ax.xaxis.set_major_formatter(date_format)

        for turnout_id, data in self.plot_data.items():
            if len(data['timestamps']) > 0 and len(data['durations']) > 0:
                sorted_indices = sorted(range(len(data['timestamps'])), key=lambda i: data['timestamps'][i])
                sorted_timestamps = [data['timestamps'][i] for i in sorted_indices]
                sorted_durations = [data['durations'][i] for i in sorted_indices]

                self.ax.plot(sorted_timestamps, sorted_durations, marker='o', linestyle='-', label=turnout_id)

        self.ax.set_xlabel('Time (HH:MM:SS)', color='black') # Ensure labels are white on update
        self.ax.set_ylabel('Duration (s)', color='black') # Ensure labels are white on update
        self.ax.set_title('Throw Time Trend', color='black') # Ensure title is white on update
        self.ax.tick_params(axis='x', colors='black')    # 设置x轴刻度颜色为白色
        self.ax.tick_params(axis='y', colors='black')    # 设置y轴刻度颜色为白色
        self.ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        plt.setp(self.ax.get_xticklabels(), rotation=45, ha='right', color='black') # Ensure tick labels are white
        self.ax.legend(loc='upper right',edgecolor='black', labelcolor='black') # Style legend
        self.ax.grid(True, color='lightgray', linestyle='-', linewidth=0.5) # Style grid
        # 强制更新x轴范围，确保所有数据点显示
        if all_timestamps:
            padding = datetime.timedelta(seconds=seconds * 0.05)  # 5%的边距
            self.ax.set_xlim(min_time - padding, max_time + padding)
        self.figure.tight_layout()
        self.toolbar.set_message = lambda s: self.toolbar.message.emit(
            f'<span style="color: black; background: #d3d3d3; border: 1px solid #2f5597;">{s}</span>'
        )
        self.canvas.draw()


    def cancelLastSelection(self):
        if self.manual_partitions:
            self.manual_partitions.pop()
            print("Last selection canceled.")
        else:
            print("No selection to cancel.")

    def stop_detection(self):
        """暂停检测但不释放摄像头资源"""
        self.is_running = False  # 设置检测停止标志

        # 停止定时器但不销毁
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        if hasattr(self, 'periodic_csv_timer') and self.periodic_csv_timer.isActive():
            self.periodic_csv_timer.stop()

        self.save_csv_on_stop()
        try:
            log_path = self.performance_monitor.save_performance_log()
            if log_path:
                print(f"性能日志已保存: {log_path}")
        except Exception as e:
            print(f"性能日志保存失败: {e}")

        # 显示暂停状态
        self.video_started = False
        self.videoLabel.setText("检测已暂停")
        self.videoLabel.setStyleSheet("""
            QLabel {
                font-size: 16px; 
                color: #666; 
                background: #f0f0f0;
                border: 1px solid #ddd;
            }
        """)
        self.videoLabel.setAlignment(QtCore.Qt.AlignCenter)

        # 更新按钮状态
        self.ui.pushButton_32.setEnabled(True)  # 启用开始按钮
        self.ui.pushButton_35.setEnabled(False)  # 禁用停止按钮

    def start_detection(self):
        # 如果已经在运行，直接返回
        if self.is_running:
            return

        try:
            camera_index_str = self.ui.comboBox_31.currentText()
            camera_index = int(camera_index_str)

        except ValueError:
            QMessageBox.warning(None, "Warning", "Invalid camera index!")
            return
        
        # 尝试打开摄像头
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        
        # 检查摄像头是否成功打开
        if not self.cap.isOpened():
            QMessageBox.critical(None, "Camera Error", 
                f"无法打开摄像头 {camera_index}！\n请检查:\n1. 摄像头是否连接\n2. 摄像头ID是否正确\n3. 摄像头是否被其他程序占用")
            if self.cap:
                self.cap.release()
                self.cap = None
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # 设置运行状态
        self.is_running = True
        self.video_started = True
        self.frame_count = 0

        self.performance_monitor.start_run()

        # 更新按钮状态
        self.ui.pushButton_32.setEnabled(False)
        self.ui.pushButton_35.setEnabled(True)

        # 清除暂停状态显示
        self.videoLabel.setText("")
        self.videoLabel.setStyleSheet("")

        # 创建或重新启动定时器
        if not hasattr(self, 'timer'):
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.captureFrame)

        self.timer.start(30)

        # 定时保存 CSV
        self.periodic_csv_timer = QTimer()
        self.periodic_csv_timer.timeout.connect(self.save_csv_periodically)
        self.periodic_csv_timer.start(30000)

    # def captureFrame(self):
    #     ret, cv_img = self.cap.read()
    #     if not ret:
    #         self.stop_detection()
    #         return
    #     if ret:
    #         self.frame_count += 1
    #         if self.frame_count % self.frame_skip == 0:
    #             self.performOCRAndColorDetection(cv_img)
    #             self.updateFrame(cv_img)
    def captureFrame(self):
        if not self.cap or not self.cap.isOpened():
            print("摄像头未正确打开，停止检测")
            self.stop_detection()
            return
        
        ret, cv_img = self.cap.read()
        
        if not ret or cv_img is None:
            print("无法读取视频帧，可能摄像头已断开连接")
            self.stop_detection()
            QMessageBox.warning(None, "视频流错误", "无法读取视频帧，检测已停止！\n请检查摄像头连接。")
            return

        self.performance_monitor.record_raw_frame()
        self.frame_count += 1
        # 非跳帧：只更新视频
        if self.frame_count % self.frame_skip != 0:
            self.updateFrame(cv_img)
            return

        # 跳帧点：做一次 OCR，然后分别更新两个标签
        perf_total_start = self.performance_monitor.start_timer() if self.performance_monitor else None
        perf_ocr_start = None
        ocr_ms = None
        success_flag = True
        try:
            if self.performance_monitor:
                perf_ocr_start = self.performance_monitor.start_timer()
            processed_frame = self.performOCRAndColorDetection(cv_img)
            if self.performance_monitor and perf_ocr_start is not None:
                ocr_ms = self.performance_monitor.stop_timer(perf_ocr_start)
            self.updateFrame(cv_img)  # 左侧原始画面
            processed_qt_img = self.convertCvToPixmap(processed_frame)
            self.ocrLabel.setPixmap(processed_qt_img.scaled(self.ocrLabel.width(),self.ocrLabel.height(),aspectRatioMode=1))
        except Exception:
            success_flag = False
            # 异常分支：如果已 start 但未 stop，需补 stop 防止悬空计时
            if self.performance_monitor and perf_ocr_start is not None and ocr_ms is None:
                ocr_ms = self.performance_monitor.stop_timer(perf_ocr_start)
            raise
        finally:
            if self.performance_monitor and perf_total_start is not None:
                total_ms = self.performance_monitor.stop_timer(perf_total_start)
                self.performance_monitor.record_metrics(
                    ocr_ms=ocr_ms,
                    total_ms=total_ms,
                    success=success_flag
                )

    # def updateFrame(self, cv_img):
    #     self.frame_height, self.frame_width = cv_img.shape[:2]
    #     qt_img = self.convertCvToPixmap(cv_img)
    #     self.videoLabel.setPixmap(qt_img.scaled(self.videoLabel.width(), self.videoLabel.height(), aspectRatioMode=1)) # self.videoLabel -> self.videoLabel
    #     self.videoLabel.raise_()
    #     self.videoLabel.update()
    #     if self.video_started:
    #         processed_frame = self.performOCRAndColorDetection(cv_img)
    #         processed_qt_img = self.convertCvToPixmap(processed_frame)
    #         self.ocrLabel.setPixmap(processed_qt_img.scaled(self.ocrLabel.width(), self.ocrLabel.height(), aspectRatioMode=1)) # self.ocrLabel -> self.ocrLabel

    def updateFrame(self, cv_img):
        self.frame_height, self.frame_width = cv_img.shape[:2]
        
        # 在原始视频帧上绘制已选择的红色框，确保每帧都显示
        if self.manual_partitions and self.videoLabel.width() > 0 and self.frame_width > 0:
            for x0, y0, x1, y1 in self.manual_partitions:
                # 将 videoLabel 坐标转换为 cv_img 坐标
                cv_x0 = int(x0 * self.frame_width / self.videoLabel.width())
                cv_y0 = int(y0 * self.frame_height / self.videoLabel.height())
                cv_x1 = int(x1 * self.frame_width / self.videoLabel.width())
                cv_y1 = int(y1 * self.frame_height / self.videoLabel.height())
                # 绘制红色框
                cv2.rectangle(cv_img, (cv_x0, cv_y0), (cv_x1, cv_y1), (0, 0, 255), 2)
        
        qt_img = self.convertCvToPixmap(cv_img)
        self.videoLabel.setPixmap(qt_img.scaled(self.videoLabel.width(),self.videoLabel.height(),aspectRatioMode=1))
        self.videoLabel.raise_()
        self.videoLabel.update()

    def convertCvToPixmap(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(qt_format)

    def performOCRAndColorDetection(self, cv_img):
        if cv_img is None or cv_img.size == 0:
            return cv_img

        detected_alert_contents = []
        detected_turnout_contents = []
        self.init_csv()
        timestamp_text = None

        # 固定时间戳区域
        timestamp_x0, timestamp_y0, timestamp_x1, timestamp_y1 = 1781, 75, 1903, 107
        timestamp_region = cv_img[timestamp_y0:timestamp_y1, timestamp_x0:timestamp_x1]
        timestamp_text = self.performOCRForTimestamp(timestamp_region)
        timestamp_text = self.format_timestamp(timestamp_text)

        for i, (x0, y0, x1, y1) in enumerate(self.manual_partitions):
            if self.videoLabel.width() == 0 or self.frame_width == 0:
                print("Error: Video frame or label width is zero. Skipping the detection.")
                continue  # 跳过无效区域

            x0, y0 = int(x0 * self.frame_width / self.videoLabel.width()), int(
                y0 * self.frame_height / self.videoLabel.height())
            x1, y1 = int(x1 * self.frame_width / self.videoLabel.width()), int(
                y1 * self.frame_height / self.videoLabel.height())

            partition_image = cv_img[y0:y1, x0:x1]

            if partition_image is None or partition_image.size == 0:
                print("Invalid partition image for OCR.")
                continue

            # 执行 OCR
            result = ocr.ocr(partition_image, cls=True)

            # 检查 OCR 结果是否有效
            if not result or not isinstance(result, list):
                print("OCR returned no results or invalid format.")
                continue

            cv2.rectangle(cv_img, (x0, y0), (x1, y1), (0, 0, 255), 2)

            for line in result:
                if not line:  # 检查 line 是否为 None 或空
                    continue

                # 确保 line 是列表或元组，并且包含至少一个元素
                if not isinstance(line, (list, tuple)) or len(line) == 0:
                    continue

                for det, text_score in line:
                    if not det or not text_score:  # 检查 det 和 text_score 是否有效
                        continue

                    text = text_score[0] if isinstance(text_score, (list, tuple)) and len(text_score) > 0 else ""
                    box = det
                    px0, py0, px1, py1 = map(int, [box[0][0], box[0][1], box[2][0], box[2][1]])
                    px0, py0, px1, py1 = px0 + x0, py0 + y0, px1 + x0, py1 + y0
                    text_region = cv_img[py0:py1, px0:px1]
                    text_color = self.getTextColor(text_region)
                    rectangle_color = self.getRectangleColor(cv_img, px0, py0, px1, py1)

                    if any(keyword.lower() in text.lower() for keyword in self.turnout_keywords):
                        detected_turnout_contents.append((text, text_color, rectangle_color))

                        if text_color == "green" and rectangle_color == "white":
                            if self.last_conversion_time:
                                current_time = time.time()
                                time_diff = current_time - self.last_conversion_time
                                self.conversion_time_diffs.append(time_diff)
                            self.last_conversion_time = time.time()

        self.displayMatchingContents(detected_alert_contents, detected_turnout_contents, timestamp_text)
        return cv_img

    def performOCRForTimestamp(self, region):
        try:
            # 图像预处理
            gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            _, processed_region = cv2.threshold(gray_region, 127, 255, cv2.THRESH_BINARY)

            result = ocr.ocr(processed_region, cls=True)

            if result and len(result) > 0 and len(result[0]) > 0:
                return result[0][0][1][0]

        except Exception as e:
            print(f"OCR Error: {str(e)}")
        return None  # 明确返回None便于后续处理

    def preprocess_timestamp_region(self, region):
        gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        processed_region = cv2.adaptiveThreshold(gray_region, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                 cv2.THRESH_BINARY, 11, 2)
        return processed_region

    # def format_timestamp(self, timestamp_text):
    #     if timestamp_text:
    #         timestamp_text = re.sub(r'(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})', r'\1.\2.\3 \4:\5:\6',
    #                                 timestamp_text)
    #         return timestamp_text
    #     return None
    def format_timestamp(self, timestamp_text):
        if timestamp_text:
            # 使用正则表达式进行更加严格的匹配
            timestamp_text = re.sub(r'(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2}):(\d{2})', r'\1.\2.\3 \4:\5:\6',
                                    timestamp_text)
            if timestamp_text:
                return timestamp_text
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 返回系统时间作为最后的备选

    def detectBlink(self, identifier, current_color, previous_colors):
        """检测闪烁，基于消失和变为灰色"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if identifier not in previous_colors:
            previous_colors[identifier] = {
                'color': current_color,
                'timestamp': timestamp
            }
            return False

        previous_color_data = previous_colors[identifier]
        previous_color = previous_color_data['color']
        previous_timestamp = previous_color_data['timestamp']

        if current_color == "gray":
            if previous_color != "gray":
                previous_colors[identifier] = {'color': current_color, 'timestamp': timestamp}
                return True
        else:
            previous_colors[identifier] = {'color': current_color, 'timestamp': timestamp}

        return False

    def getTextColor(self, region):
        avg_color = np.mean(region.reshape(-1, 3), axis=0)
        if np.all(avg_color < 50):
            return "black"
        diff = np.abs(avg_color - np.array([80, 80, 80]))
        if np.sum(diff) < 50:
            return "gray"
        elif avg_color[2] > avg_color[1] and avg_color[2] > avg_color[0]:
            return "red"
        elif avg_color[1] > avg_color[0] and avg_color[1] > avg_color[2]:
            return "green"
        elif avg_color[0] > avg_color[1] and avg_color[0] > avg_color[2]:
            return "blue"
        else:
            return "other"

    def getRectangleColor(self, image, x0, y0, x1, y1):
        margin = 5
        x0, y0 = max(0, x0 + margin), max(0, y0 + margin)
        x1, y1 = min(image.shape[1], x1 - margin), min(image.shape[0], y1 - margin)

        region = image[y0:y1, x0:x1]
        avg_color = np.mean(region.reshape(-1, 3), axis=0)
        blue, green, red = avg_color

        if np.allclose(avg_color, [80, 80, 80], atol=30):
            return "gray"
        if red > 200 and green > 200 and blue < 150 and abs(red - green) < 50:
            return "yellow"
        elif red > 150 and red > green * 1.2 and red > blue * 1.2:
            return "red"
        elif green > 150 and green > red * 1.3 and green > blue * 1.3:
            return "green"
        elif blue > 150 and blue > red * 1.3 and blue > green * 1.3:
            return "blue"
        elif red > 120 and red < 200 and green > 120 and blue > 115 and max(abs(red - green), abs(green - blue), abs(blue - red)) < 80:
            return "white"
        elif max(abs(red - green), abs(green - blue), abs(blue - red)) < 35 and red > 100 and green > 100 and blue > 100:
            return "gray"
        else:
            return "other"

    # def stop_detection(self):
    #     """暂停检测但不释放摄像头资源"""
    #     self.is_running = False  # 设置检测停止标志
    #     self.timer.stop()  # 停止检测定时器
    #
    #     # 保持摄像头连接（移除release和置空操作）
    #     # if self.cap:
    #     #     self.cap.release()
    #     #     self.cap = None
    #
    #     # 显示暂停状态 - 使用 videoLabel 属性（已在 __init__ 中定义）
    #     self.videoLabel.setText("检测已暂停")
    #     self.videoLabel.setStyleSheet("""
    #         QLabel {
    #             font-size: 16px;
    #             color: #666;
    #             background: #f0f0f0;
    #             border: 1px solid #ddd;
    #         }
    #     """)
    #     self.videoLabel.setAlignment(QtCore.Qt.AlignCenter)

    def play_sound_alert(self):
        selected_row = self.ui.tableWidget_3.currentRow() # self.turnoutTable -> self.ui.tableWidget_3
        if selected_row == -1:
            QMessageBox.warning(self.ui.frame_20, "No Selection", "Please select a row to play the sound alert.") # self -> self.ui.frame_20, using frame_20 as parent
            return
        try:
            winsound.Beep(1000, 500)
        except Exception as e:
            QMessageBox.critical(self.ui.frame_20, "Error", f"Failed to play sound: {e}") # self -> self.ui.frame_20

    def send_notification(self):
        selected_row = self.ui.tableWidget_3.currentRow() # self.turnoutTable -> self.ui.tableWidget_3
        if selected_row == -1:
            QMessageBox.warning(self.ui.frame_20, "No Selection", "Please select a row to send a notification.") # self -> self.ui.frame_20
            return

        ocr_data = []
        for col in range(self.ui.tableWidget_3.columnCount()): # self.turnoutTable -> self.ui.tableWidget_3
            item = self.ui.tableWidget_3.item(selected_row, col) # self.turnoutTable -> self.ui.tableWidget_3
            ocr_data.append(item.text() if item else "")

        message = f"Turnout ID: {ocr_data[0]}\nDate/Time: {ocr_data[1]}\nStatus: {ocr_data[2]}\nThrow Time: {ocr_data[3]}\nText: {ocr_data[4]}"

        webhook_url = self.settings.get("WeChat Webhook URL")
        if not webhook_url:
            # print("WeChat Webhook URL not configured. Skipping notification.")
            return

        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }

        try:
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 200:
                QMessageBox.information(None, "Notification Sent", "The notification was sent successfully.") # self -> self.ui.frame_20
            else:
                QMessageBox.warning(self.ui.frame_20, "Error", f"Failed to send notification. Status code: {response.status_code}") # self -> self.ui.frame_20
        except Exception as e:
            QMessageBox.critical(self.ui.frame_20, "Error", f"An error occurred while sending the notification: {e}") # self -> self.ui.frame_20

    def send_email(self):
        row = self.ui.tableWidget_3.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to send an email.")
            return

        ocr_data = []
        for col in range(self.ui.tableWidget_3.columnCount()): # self.turnoutTable -> self.ui.tableWidget_3
            item = self.ui.tableWidget_3.item(row, col) # self.turnoutTable -> self.ui.tableWidget_3
            ocr_data.append(item.text() if item else "")

        receiver_email = self.settings.get("Receiver Email")
        smtp_server = self.settings.get("Smtp server")
        smtp_port = int(self.settings.get("Smtp port"))
        sender_email = self.settings.get("Sender email")
        sender_password = self.settings.get("Sender password")

        if not all([receiver_email, smtp_server, sender_email, sender_password]):
            # print("Email settings are not fully configured. Skipping email notification.")
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        subject = f"OCR Notification - {timestamp}"
        body = (
            f"The following Turnout results were detected (Timestamp: {timestamp}):\n\n"
            f"Date/Time: {ocr_data[0]}\n"
            f"Area: {ocr_data[1]}\n"
            f"Sub Area: {ocr_data[2]}\n"
            f"Object: {ocr_data[3]}\n"
            f"Text: {ocr_data[4]}\n"
        )

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            server.login(sender_email, sender_password)
            server.send_message(message)
            server.quit()
            QMessageBox.information(None, "Email Sent", "The email was sent successfully.")
        except smtplib.SMTPAuthenticationError:
            QMessageBox.warning(None, "Error", "Authentication failed. Check your email address and SMTP authorization code.")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to send email: {e}")

    def displayMatchingContents(self, alert_contents, turnout_contents, timestamp_text):
        if timestamp_text is None:
            timestamp_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for text, text_color, rect_color in turnout_contents:
            # 检查识别的文本是否包含预设的道岔编号
            matched_turnout_id = None
            for turnout_id in self.turnout_keywords:
                if turnout_id in text:  # 检查预设ID是否在识别文本中
                    matched_turnout_id = turnout_id
                    break

            # 如果没有匹配到预设的道岔编号，则跳过不显示
            if not matched_turnout_id:
                continue

            feedback_text = self.getFeedbackForText(text_color)
            feedback_rect = self.getFeedbackForRectangle(rect_color)

            row_position = self.ui.tableWidget_3.rowCount() # self.turnoutTable -> self.ui.tableWidget_3
            self.ui.tableWidget_3.insertRow(row_position) # self.turnoutTable -> self.ui.tableWidget_3

            status = ""
            throw_time = 0

            try:
                current_time = datetime.datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S")
            except:
                current_time = datetime.datetime.now()

            if text_color == "green":
                status = "Normal"
            elif text_color == "blue":
                status = "Reverse"
            elif text_color == "red":
                status = "Failed"
            else:
                status = "Unknown"

            if matched_turnout_id  in self.turnout_status:
                prev_data = self.turnout_status[matched_turnout_id]
                prev_color = prev_data['text_color']
                prev_time = prev_data['time']

                if prev_color != text_color and prev_color in ['blue', 'green'] and text_color in ['blue', 'green']:
                    time_diff = current_time - prev_time
                    throw_time = time_diff.total_seconds()
                    del self.turnout_status[matched_turnout_id]

            if text_color in ['blue', 'green']:
                self.turnout_status[matched_turnout_id] = {
                    'text_color': text_color,
                    'time': current_time
                }

            self.ui.tableWidget_3.setItem(row_position, 0, QTableWidgetItem(matched_turnout_id)) # self.turnoutTable -> self.ui.tableWidget_3
            self.ui.tableWidget_3.setItem(row_position, 1, QTableWidgetItem(timestamp_text)) # self.turnoutTable -> self.ui.tableWidget_3
            self.ui.tableWidget_3.setItem(row_position, 2, QTableWidgetItem(status)) # self.turnoutTable -> self.ui.tableWidget_3
            self.ui.tableWidget_3.setItem(row_position, 3, QTableWidgetItem(f"{throw_time:.2f}s")) # self.turnoutTable -> self.ui.tableWidget_3
            self.ui.tableWidget_3.setItem(row_position, 4, QTableWidgetItem(feedback_text)) # self.turnoutTable -> self.ui.tableWidget_3

            self.save_to_csv(matched_turnout_id, timestamp_text, status, throw_time, feedback_text)

            if throw_time > 0:
                self.update_plot_data(matched_turnout_id, current_time, throw_time)
                self.update_chart()
        # 添加自动滚动功能
        if self.auto_scroll_enabled:
            self.turnoutTable.scrollToBottom()

    def init_csv(self):

        output_folder = "output_data"
        os.makedirs(output_folder, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        csv_file_path = os.path.join(output_folder, f"turnout_ocr_results_{timestamp}.csv")

        if not hasattr(self, 'csv_writer') or self.csv_writer is None:
            self.csv_file = open(csv_file_path, mode='a', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)

            if self.csv_file.tell() == 0:
                self.csv_writer.writerow(["Turnout ID", "Date/Time", "Status", "Throw Time", "Text"])

                print(f"CSV file created: {csv_file_path}")

    def save_csv_on_stop(self):
        if self.csv_file:
            try:
                self.csv_file.flush()
                print("CSV 数据已在停止时保存。")
            except Exception as e:
                print(f"停止时保存 CSV 出错: {e}")

    def save_csv_periodically(self):
        if self.csv_file:
            try:
                self.csv_file.flush()
                print("CSV 数据已定期保存。")
            except Exception as e:
                print(f"定期保存 CSV 出错: {e}")

    # def save_to_csv(self, turnout_id, timestamp_text, status, throw_time, feedback_text):
    #     if self.csv_writer:
    #         try:
    #             self.csv_writer.writerow([turnout_id, timestamp_text, status, throw_time, feedback_text])
    #         except Exception as e:
    #             print(f"Write to CSV exception: {e}")

    # 这个函数会不断向csv文件中更新，随时打开随时更新
    def save_to_csv(self, turnout_id, timestamp_text, status, throw_time, feedback_text):
        if self.csv_file:
            self.csv_writer.writerow([turnout_id, timestamp_text, status, throw_time, feedback_text])
            self.csv_file.flush()
                        
            # 【新增】同步推送到AI Assistant
            if push_turnout_data:
                try:
                    push_turnout_data(turnout_id, timestamp_text, status, throw_time, feedback_text)
                except:
                    pass

    def getFeedbackForText(self, color):
        feedback_map = {
            "gray": "No data available",
            "green": "Not disturbed, Element available, Normal position",
            "blue": "Not disturbed, Element available, Reverse position",
            "red": "Disturbed, Element not available",
            "black": "Not disturbed, Element available, Not supervised",
            "blink": "Discrepancy",
            "other": "No issue detected"
        }
        return feedback_map.get(color, "Unknown feedback")

    def getFeedbackForRectangle(self, color):
        feedback_map_rect = {
            "yellow": "Blocked against throwing",
            "gray": "No data available",
            "white": "Blocked by route / overlap or flank protection",
            "red": "Disturbed",
            "green": "Not disturbed",
            "blink": "Discrepancy",
            "other": "Not blocked"
        }
        return feedback_map_rect.get(color, "Unknown feedback")

    def resetDetectionRegion(self):
        try:
            self.manual_partitions.clear()
            print("Detection regions have been reset.")
            # No need to update here, paintEvent in main.py will handle redraw based on manual_partitions
        except Exception as e:
            print(f"An error occurred while resetting detection regions: {e}")

    # -------- Setting Functions --------
    def set_turnout_ids(self):
        """更新当前选中车站的道岔编号"""
        current_station = self.ui.comboBox_28.currentText()
        input_ids = self.ui.lineEdit_4.text().strip()

        if current_station and input_ids:
            # 更新内存中的映射
            self.station_turnout_map[current_station] = input_ids
            # 更新当前设置
            self.turnout_ids_setting = input_ids
            self.turnout_keywords = set([tid.strip() for tid in input_ids.split(',')])

    def set_wechat_webhook_url(self):
        webhook_url = self.ui.lineEdit_6.text().strip()
        if webhook_url:
            self.settings["WeChat Webhook URL"] = webhook_url
            # QMessageBox.information(None, "设置已更新", "企业微信 Webhook URL 已临时更新。")
        else:
            return
            # QMessageBox.warning(None, "输入无效", "请输入有效的 Webhook URL。")

    def set_receiver_email(self):
        input_email = self.ui.lineEdit_7.text().strip()
        if input_email:
            # 只更新内存中的 settings 字典
            self.settings["Receiver Email"] = input_email
            # QMessageBox.information(None, "设置已更新", "收件人邮箱已临时更新。")
        else:
            return
            # QMessageBox.warning(None, "输入无效", "请输入有效的邮箱地址。")

    def set_smtp_settings(self):
        server = self.ui.lineEdit_8.text().strip()
        port_str = self.ui.lineEdit_9.text().strip()
        sender_email = self.ui.lineEdit_10.text().strip()
        password = self.ui.lineEdit_11.text().strip()

        if not all([server, port_str, sender_email, password]):
            # QMessageBox.warning(None, "输入无效", "请填写所有SMTP设置字段。")
            return

        try:
            port = int(port_str)
            # 只更新内存中的 settings 字典
            self.settings["Smtp server"] = server
            self.settings["Smtp port"] = str(port)
            self.settings["Sender email"] = sender_email
            self.settings["Sender password"] = password
            # QMessageBox.information(None, "设置已更新", "SMTP 设置已临时更新。")

        except ValueError:
            return
            # QMessageBox.warning(None, "输入无效", "请输入一个有效的端口号。")

    # def set_abnormal_dwell_time(self): # Dummy function as dwell time is not relevant for Turnout, keeping for consistency if copy-pasting from train.py
    #     QMessageBox.information(None, "Setting Info", "Abnormal Dwell Time setting is not applicable for Turnout.")

    # Dummy functions for chart operations - to be implemented if toolbar buttons are directly used or custom logic is needed.
    def reset_original_view(self):
        print("Reset original view function to be implemented")
        self.toolbar.home()

    def back_to_previous_view(self):
        print("Back to previous view function to be implemented")
        self.toolbar.back()

    def forward_to_next_view(self):
        print("Forward to next view function to be implemented")
        self.toolbar.forward()

    def pan_chart(self):
        print("Pan chart function to be implemented")
        self.toolbar.pan()

    def zoom_to_rectangle(self):
        print("Zoom to rectangle function to be implemented")
        self.toolbar.zoom()

    def configures_subplots(self):
        print("Configures subplots function to be implemented")
        self.toolbar.configure_subplots()

    def edit_axis_curve_image_parameters(self):
        self.toolbar.edit_parameters() # Corrected method name

    def save_figure(self):
        print("Save the figure function to be implemented")
        self.toolbar.save_figure()

    def eventFilter(self, obj, event):
        if obj is self.videoLabel:
            # 鼠标按下事件
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.is_selecting = True
                self.start_x = event.x()
                self.start_y = event.y()
                self.end_x = self.start_x
                self.end_y = self.start_y
                return True

            # 鼠标移动事件
            elif event.type() == QEvent.MouseMove and self.is_selecting:
                self.end_x = event.x()
                self.end_y = event.y()
                self.videoLabel.update()
                return True

            # 鼠标释放事件
            elif event.type() == QEvent.MouseButtonRelease and self.is_selecting and event.button() == Qt.LeftButton:
                self.is_selecting = False
                # 调整坐标顺序并验证有效性
                x0 = min(self.start_x, self.end_x)
                x1 = max(self.start_x, self.end_x)
                y0 = min(self.start_y, self.end_y)
                y1 = max(self.start_y, self.end_y)

                # 确保最小有效区域
                if (x1 - x0 > 1) and (y1 - y0 > 1):
                    self.manual_partitions.append((x0, y0, x1, y1))
                self.videoLabel.update()
                return True

            # 绘制选择框
            elif event.type() == QEvent.Paint and self.is_selecting:
                painter = QPainter(self.videoLabel)
                painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
                rx = min(self.start_x, self.end_x)
                ry = min(self.start_y, self.end_y)
                rw = abs(self.end_x - self.start_x)
                rh = abs(self.end_y - self.start_y)
                painter.drawRect(rx, ry, rw, rh)
                return False

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event): # These mouse events will be handled by main.py on frame_20 using event filter
        pass

    def mouseMoveEvent(self, event):
        pass

    def mouseReleaseEvent(self, event):
        pass

    def close_all(self):
        # 程序退出时主动停止检测并生成性能日志
        try:
            self.stop_detection()
        except Exception as e:
            print(f"关闭道岔检测时出现异常: {e}")

        if self.cap:
            self.cap.release()
            self.cap = None
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None