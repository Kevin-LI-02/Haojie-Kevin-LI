# alarmlist.py

import sys
import os
import csv
import time
import difflib
import smtplib
import winsound
import threading
import cv2
import subprocess
import requests
from collections import deque
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox, QVBoxLayout, QAbstractItemView
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from paddleocr import PaddleOCR
from PyQt5.QtCore import pyqtSignal
from performance_monitor import PerformanceMonitor

# 导入实时推送模块
try:
    from realtime_push import push_alarmlist_data
except ImportError:
    print("Warning: realtime_push module not found, data push disabled")
    push_alarmlist_data = None



class AlarmListIntegration(QtCore.QObject):
    """
    将 Alarmlist 的核心逻辑放到这里，
    并在主程序中通过 from alarmlist import AlarmListIntegration 来使用。
    """
    update_video_signal = pyqtSignal(QtGui.QImage)
    update_ocr_signal = pyqtSignal(QtGui.QImage)


    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.alarm_table = self.ui.tableWidget_2
        self.auto_scroll_enabled = True  # 添加自动滚动标志

        # 修改：使用deque来存储报警信息，最大长度为100
        self.last_alerts_sent = deque(maxlen=50)  # 使用deque替代set，最大长度100

        self.ocr = None
        self.ocr_ready = False  # OCR模型加载状态

        self.stop_flag = False  # 是否请求终止当前识别
        self.update_video_signal.connect(self.update_video)
        self.update_ocr_signal.connect(self.update_ocr)

        self.settings = self.load_settings_from_csv("default account.csv")
        if not self.settings:
            # 如果加载失败，可以给出提示或者使用默认值
            print("Warning: Could not load settings from 'default account.csv'. Using default values.")
            # 在这里可以设置一些备用/默认的参数
            self.settings = {
                "WeChat Webhook URL": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=b05a8fb5-5469-49b1-ad91-7fbc0738eb26",
                "Receiver Email": "eal.bjtu@gmail.com",
                "Smtp server": "smtp.163.com",
                "Smtp port": "465",
                "Sender email": "lihaojie0044@163.com",
                "Sender password": "AQri6kUXQ4tK9nNC"
            }

        # 1) 设置 frame_13、frame_14 的样式：无圆角、背景 #2f5597
        self.ui.frame_13.setStyleSheet("border-radius: 0px; background-color: #2f5597;")
        self.ui.frame_14.setStyleSheet("border-radius: 0px; background-color: #2f5597;")

        # 设置 comboBox_34 的默认值为5
        self.ui.comboBox_34.setCurrentText("5")

        # 2) 在 frame_13、frame_14 中使用布局添加 QLabel，分别显示“左侧视频”和“右侧OCR”画面
        self.video_label = QtWidgets.QLabel()
        self.video_label.setScaledContents(True)
        layout13 = QVBoxLayout(self.ui.frame_13)
        layout13.setContentsMargins(0, 0, 0, 0)
        layout13.addWidget(self.video_label)

        self.ocr_label = QtWidgets.QLabel()
        self.ocr_label.setScaledContents(True)
        layout14 = QVBoxLayout(self.ui.frame_14)
        layout14.setContentsMargins(0, 0, 0, 0)
        layout14.addWidget(self.ocr_label)

        # 3) 初始化表格 tableWidget_2
        # self.ui.tableWidget_2.setColumnCount(5)
        # self.ui.tableWidget_2.setHorizontalHeaderLabels(["Date/Time", "Area", "Sub Area", "Object", "Text"])
        self.ui.tableWidget_2.setColumnCount(6)
        self.ui.tableWidget_2.setHorizontalHeaderLabels(["Date/Time", "Area", "Sub Area", "Object", "Text", "Action"])

        self.ui.tableWidget_2.setRowCount(0)
        self.ui.tableWidget_2.horizontalHeader().setVisible(True)
        self.ui.tableWidget_2.verticalHeader().setVisible(True)
        # 行选择模式
        self.ui.tableWidget_2.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.tableWidget_2.setSelectionMode(QAbstractItemView.SingleSelection)

        # 4) 绑定按钮
        self.ui.pushButton_19.clicked.connect(self.start_detection)  # Start
        self.ui.pushButton_20.clicked.connect(self.stop_detection)  # Stop
        self.ui.pushButton_21.clicked.connect(self.send_notification)  # Send Notification
        self.ui.pushButton_22.clicked.connect(self.send_email)  # Send Email
        self.ui.pushButton_23.clicked.connect(self.play_sound_alert)  # Sound Alert
        self.ui.pushButton_27.clicked.connect(self.toggle_mute)  # Mute
        # 绑定Setting页面按钮
        self.ui.pushButton_53.clicked.connect(self.set_wechat_webhook_url)
        self.ui.pushButton_54.clicked.connect(self.set_receiver_email)
        self.ui.pushButton_55.clicked.connect(self.set_smtp_settings)

        # 5) 核心参数
        self.cap = None
        self.is_running = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_frame)
        self.frame_count = 0
        self.skip_frames = 10  # GPU优化：10帧跳帧，约0.3-0.4秒检测一次（平衡实时性和性能）
        self.process_time_threshold = 0.1
        self.last_process_time = 0

        self.csv_writer = None
        self.csv_file = None

        # 用于存储上一帧识别的三行结果，避免重复插入
        self.last_ocr_results = [None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None]  # 5行结果存储
        # OCR - 延迟初始化，避免界面卡顿（在start_detection时异步初始化）
        # self.ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=True)  # 已移除同步初始化


        # 是否静音
        self.is_muted = False

        # OCR 线程
        self.ocr_thread = None

        # 定义警报信息及其优先级
        self.alerts_priority = self.load_alerts_priority_from_csv("alerts_priority.csv")
        self.performance_monitor = PerformanceMonitor(
            module_name="AlarmList Detection",
            log_dir=os.path.join("performance_logs", "alarmlist"),
        )


    def init_ocr_model(self):
        try:
            print("Initializing OCR model...")
            # 明确启用GPU加速
            self.ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=True)
            self.ocr_ready = True
            print("OCR model loaded successfully with GPU.")
        except Exception as e:
            print(f"OCR model failed to load: {e}")
            self.ocr_ready = False

    def update_video(self, qimg):
        self.video_label.setPixmap(QtGui.QPixmap.fromImage(qimg))

    def update_ocr(self, qimg2):
        self.ocr_label.setPixmap(QtGui.QPixmap.fromImage(qimg2))

    def set_station(self, station: str):
        """
        设置当前站点并更新所有必要的配置。
        当站点下拉框变化时，此方法被调用。
        """
        self.current_station = station
        print(f"告警列表（Alarm List）的站点已设置为: {self.current_station}")

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
            print(f"Settings loaded successfully from {filename}.")
            return settings
        except FileNotFoundError:
            print(f"Error: The file {filename} was not found.")
            return None
        except Exception as e:
            print(f"An error occurred while reading {filename}: {e}")
            return None

    # ========== Setting Page Functions ==========
    def load_alerts_priority_from_csv(self, csv_file_path):
        """
        从CSV文件加载报警信息、优先级和操作方法
        格式：Alert Text,Priority,Action
        自动兼容 UTF-8 / UTF-8-SIG / GBK 编码
        """
        alerts_info = {}
        try:
            if not os.path.exists(csv_file_path):
                print(f"⚠️ File {csv_file_path} not found.")
                return alerts_info

            # 尝试不同编码方式读取
            for enc in ['utf-8', 'utf-8-sig', 'gbk']:
                try:
                    with open(csv_file_path, mode='r', encoding=enc) as file:
                        reader = csv.reader(file)
                        header = next(reader, None)
                        for row in reader:
                            if len(row) >= 2:
                                alert_text = row[0].strip()
                                try:
                                    priority = int(row[1].strip())
                                except ValueError:
                                    priority = 3  # 默认优先级
                                action = row[2].strip() if len(row) >= 3 else "无对应操作建议（待补充）"
                                alerts_info[alert_text] = {"priority": priority, "action": action}
                        print(f"✅ Loaded {len(alerts_info)} alerts from {csv_file_path} (encoding={enc})")
                        return alerts_info
                except UnicodeDecodeError:
                    continue  # 换下一个编码尝试

            print(f"❌ All decoding attempts failed for {csv_file_path}. Please save it as UTF-8.")
        except Exception as e:
            print(f"❌ Error loading alerts priority from CSV: {e}")

        return alerts_info

    # def load_alerts_priority_from_csv(self, csv_file_path):
    #     """
    #     从CSV文件加载报警信息及优先级
    #     CSV文件格式：Alert Text,Priority
    #     返回字典：{报警文本: 优先级}
    #     """
    #     alerts_priority = {}
    #     try:
    #         if os.path.exists(csv_file_path):
    #             with open(csv_file_path, mode='r', encoding='utf-8') as file:
    #                 reader = csv.reader(file)
    #                 # 跳过表头（如果存在）
    #                 try:
    #                     header = next(reader)
    #                     # 检查表头格式
    #                     if len(header) < 2 or header[0].lower() != "alert text" or header[1].lower() != "priority":
    #                         print("Warning: CSV header format may be incorrect. Expected: 'Alert Text,Priority'")
    #                 except StopIteration:
    #                     # 文件为空
    #                     print("Warning: Alerts priority CSV file is empty.")
    #                     return alerts_priority
    #
    #                 for row in reader:
    #                     if len(row) >= 2:
    #                         alert_text = row[0].strip()
    #                         try:
    #                             priority = int(row[1].strip())
    #                             alerts_priority[alert_text] = priority
    #                         except ValueError:
    #                             print(f"Invalid priority value in CSV: {row[1]}")
    #             print(f"Loaded {len(alerts_priority)} alerts from {csv_file_path}")
    #         else:
    #             print(f"Warning: Alerts priority file not found at {csv_file_path}. Using empty dictionary.")
    #             # # 创建示例文件以便用户参考格式
    #             # with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
    #             #     writer = csv.writer(f)
    #             #     writer.writerow(["Alert Text", "Priority"])
    #             #     writer.writerow(["Set train dwell and trip time", 3])
    #             #     writer.writerow(["S8: Point did not move from right in time", 1])
    #             #     print(f"Created sample alerts_priority.csv at {csv_file_path}")
    #     except Exception as e:
    #         print(f"Error loading alerts priority from CSV: {e}")
    #         # 如果加载失败，可以在这里设置默认值或空字典
    #         alerts_priority = {}
    #
    #     return alerts_priority



    # ========== Setting Page Functions ==========

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

    # ========== 按钮相关函数 ==========

    def start_detection(self):
        if self.is_running:
            return

        self.stop_flag = False  # 清除旧的停止标志

        # 从 comboBox 获取摄像头索引
        try:
            camera_index_str = self.ui.comboBox_30.currentText()
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
        
        # 尝试读取一帧测试摄像头是否真正可用
        ret, test_frame = self.cap.read()
        if not ret or test_frame is None:
            QMessageBox.critical(None, "Camera Error", 
                f"摄像头 {camera_index} 无法读取视频流！\n该摄像头可能没有视频源。")
            self.cap.release()
            self.cap = None
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # 摄像头预热，减少黑屏
        for _ in range(5):
            self.cap.read()

        self.is_running = True
        self.frame_count = 0
        self.skip_frames = 10  # GPU优化：初始跳帧设置为10（与最小值保持一致）
        self.performance_monitor.start_run()

        self.init_csv()

        # 启动定时保存 CSV
        self.periodic_csv_timer = QTimer()
        self.periodic_csv_timer.timeout.connect(self.save_csv_periodically)
        self.periodic_csv_timer.start(30000)  # 每 30 秒保存一次 CSV

        # 异步初始化OCR模型
        threading.Thread(target=self.init_ocr_model).start()

        self.timer.start(30)  # 启动定时器，每30ms处理一帧

    def stop_detection(self):
        self.is_running = False
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        if hasattr(self, 'periodic_csv_timer') and self.periodic_csv_timer.isActive():
            self.periodic_csv_timer.stop()
        # 设置中断标志
        self.stop_flag = True

        # 在停止时保存 CSV 文件
        self.save_csv_on_stop()
        try:
            log_path = self.performance_monitor.save_performance_log()
            if log_path:
                print(f"性能日志已保存: {log_path}")
        except Exception as e:
            print(f"性能日志保存失败: {e}")

        self.video_label.setText("检测已暂停")
        self.video_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #666;
                background: #f0f0f0;
                border: 1px solid #ddd;
            }
        """)
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)

    def save_csv_on_stop(self):
        if self.csv_writer:
            try:
                print("正在停止时保存 CSV 数据。")
                self.csv_file.flush()  # 刷新缓冲区数据到文件
            except Exception as e:
                print(f"停止时保存 CSV 出错: {e}")

    def send_notification(self):
        # 手动发送企业微信通知(基于当前表格选中行)
        row = self.ui.tableWidget_2.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to send a notification.")
            return

        data = []
        for col in range(self.ui.tableWidget_2.columnCount()):
            item = self.ui.tableWidget_2.item(row, col)
            data.append(item.text() if item else "")

        message = f"Date/Time: {data[0]}\nArea: {data[1]}\nSub Area: {data[2]}\nObject: {data[3]}\nText: {data[4]}"

        # 这里演示企业微信Webhook
        webhook_url = self.settings.get("WeChat Webhook URL")
        if not webhook_url:
            print("WeChat Webhook URL not configured. Skipping notification.")
            return

        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }

        try:
            resp = requests.post(webhook_url, json=payload)
            if resp.status_code == 200:
                QMessageBox.information(None, "Notification", "The notification was sent successfully.")
            else:
                QMessageBox.warning(None, "Error", f"Failed to send notification. Status code: {resp.status_code}")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"An error occurred while sending the notification: {e}")

    def send_email(self):
        # 手动发送邮件(基于当前表格选中行)
        row = self.ui.tableWidget_2.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to send an email.")
            return

        data = []
        for col in range(self.ui.tableWidget_2.columnCount()):
            item = self.ui.tableWidget_2.item(row, col)
            data.append(item.text() if item else "")

        receiver_email = self.settings.get("Receiver Email")
        smtp_server = self.settings.get("Smtp server")
        smtp_port = int(self.settings.get("Smtp port"))
        sender_email = self.settings.get("Sender email")
        sender_password = self.settings.get("Sender password")

        if not all([receiver_email, smtp_server, sender_email, sender_password]):
            print("Email settings are not fully configured. Skipping email notification.")
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        subject = f"OCR Notification - {timestamp}"
        body = (
            f"The following Alarmlist results were detected (Timestamp: {timestamp}):\n\n"
            f"Date/Time: {data[0]}\n"
            f"Area: {data[1]}\n"
            f"Sub Area: {data[2]}\n"
            f"Object: {data[3]}\n"
            f"Text: {data[4]}\n"
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
            QMessageBox.warning(None, "Error",
                                "Authentication failed. Check your email address and SMTP authorization code.")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to send email: {e}")

    def play_sound_alert(self):

        row = self.ui.tableWidget_2.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to play sound alert.")
            return

        try:
            winsound.Beep(1000, 500)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to play sound: {e}")

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.ui.pushButton_27.setText("Unmute")
        else:
            self.ui.pushButton_27.setText("Mute")

    # ========== 核心OCR检测逻辑 ==========
    def process_frame(self):
        if not self.cap or self.stop_flag:
            return
        
        if not self.cap.isOpened():
            print("摄像头未正确打开，停止检测")
            self.stop_detection()
            return

        ret, frame = self.cap.read()
        
        if not ret or frame is None:
            print("无法读取视频帧，可能摄像头已断开连接")
            self.stop_detection()
            QMessageBox.warning(None, "视频流错误", "无法读取视频帧，检测已停止！\n请检查摄像头连接。")
            return

        self.performance_monitor.record_raw_frame()

        # 从 comboBox_34 获取要检测的区域数量 (默认5个)
        try:
            regions_count = int(self.ui.comboBox_34.currentText())
            regions_count = max(1, min(20, regions_count))  # 确保在1-20范围内
        except:
            regions_count = 5  # 默认值

        # 原始定义的20个区域
        full_regions_list  = [
            [(0, 615, 200, 20), (310, 615, 100, 20), (450, 615, 100, 20), (600, 615, 100, 20), (930, 615, 600, 20)],
            [(0, 635, 200, 20), (310, 635, 100, 20), (450, 635, 100, 20), (600, 635, 100, 20), (930, 635, 600, 20)],
            [(0, 655, 200, 20), (310, 655, 100, 20), (450, 655, 100, 20), (600, 655, 100, 20), (930, 655, 600, 20)],
            [(0, 674, 200, 20), (310, 674, 100, 20), (450, 674, 100, 20), (600, 674, 100, 20), (930, 674, 600, 20)],
            [(0, 691, 200, 20), (310, 691, 100, 20), (450, 691, 100, 20), (600, 691, 100, 20), (930, 691, 600, 20)],
            [(0, 711, 200, 20), (310, 711, 100, 20), (450, 711, 100, 20), (600, 711, 100, 20), (930, 711, 600, 20)],
            [(0, 731, 200, 20), (310, 731, 100, 20), (450, 731, 100, 20), (600, 731, 100, 20), (930, 731, 600, 20)],
            [(0, 749, 200, 20), (310, 749, 100, 20), (450, 749, 100, 20), (600, 749, 100, 20), (930, 749, 600, 20)],
            [(0, 769, 200, 20), (310, 769, 100, 20), (450, 769, 100, 20), (600, 769, 100, 20), (930, 769, 600, 20)],
            [(0, 787, 200, 20), (310, 787, 100, 20), (450, 787, 100, 20), (600, 787, 100, 20), (930, 787, 600, 20)],
            [(0, 807, 200, 20), (310, 807, 100, 20), (450, 807, 100, 20), (600, 807, 100, 20), (930, 807, 600, 20)],
            [(0, 827, 200, 20), (310, 827, 100, 20), (450, 827, 100, 20), (600, 827, 100, 20), (930, 827, 600, 20)],
            [(0, 845, 200, 20), (310, 845, 100, 20), (450, 845, 100, 20), (600, 845, 100, 20), (930, 845, 600, 20)],
            [(0, 865, 200, 20), (310, 865, 100, 20), (450, 865, 100, 20), (600, 865, 100, 20), (930, 865, 600, 20)],
            [(0, 882, 200, 20), (310, 882, 100, 20), (450, 882, 100, 20), (600, 882, 100, 20), (930, 882, 600, 20)],
            [(0, 900, 200, 20), (310, 900, 100, 20), (450, 900, 100, 20), (600, 900, 100, 20), (930, 900, 600, 20)],
            [(0, 920, 200, 20), (310, 920, 100, 20), (450, 920, 100, 20), (600, 920, 100, 20), (930, 920, 600, 20)],
            [(0, 940, 200, 20), (310, 940, 100, 20), (450, 940, 100, 20), (600, 940, 100, 20), (930, 940, 600, 20)],
            [(0, 960, 200, 20), (310, 960, 100, 20), (450, 960, 100, 20), (600, 960, 100, 20), (930, 960, 600, 20)],
            [(0, 980, 200, 20), (310, 980, 100, 20), (450, 980, 100, 20), (600, 980, 100, 20), (930, 980, 600, 20)],
        ]

        # 根据选择的区域数量，从底部开始取相应数量的区域
        regions_list = full_regions_list[-regions_count:]

        # 优先更新视频画面（避免等待OCR）
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        qimg = QtGui.QImage(rgb_frame.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
        self.video_label.setPixmap(QtGui.QPixmap.fromImage(qimg))

        # OCR区域预绘制框（提前显示在 ocr_label）
        frame_with_roi = frame.copy()
        for regions in regions_list:
            for (x, y, w, h) in regions:
                cv2.rectangle(frame_with_roi, (x, y), (x + w, y + h), (0, 255, 0), 2)

        roi_rgb = cv2.cvtColor(frame_with_roi, cv2.COLOR_BGR2RGB)
        h2, w2, ch2 = roi_rgb.shape
        qimg2 = QtGui.QImage(roi_rgb.data, w2, h2, ch2 * w2, QtGui.QImage.Format_RGB888)
        self.ocr_label.setPixmap(QtGui.QPixmap.fromImage(qimg2))

        self.frame_count += 1
        if self.frame_count < 30:
            pass  # 前30帧不跳过
        elif self.frame_count % self.skip_frames != 0:
            return

        start_time = time.time()


        # OCR异步执行，不卡住主线程（确保OCR模型已初始化）
        if not self.stop_flag and self.ocr_ready and (self.ocr_thread is None or not self.ocr_thread.is_alive()):
            self.ocr_thread = threading.Thread(target=self.process_ocr, args=(frame.copy(), regions_list))
            self.ocr_thread.start()

        end_time = time.time()
        self.last_process_time = end_time - start_time

        if self.last_process_time > self.process_time_threshold:
            self.skip_frames = min(self.skip_frames + 1, 20)  # GPU优化：最大跳帧从50降至20
        else:
            self.skip_frames = max(self.skip_frames - 1, 10)  # GPU优化：最小跳帧从5提升至10


    def process_ocr(self, frame, regions_list):
        perf_total_start = self.performance_monitor.start_timer()
        perf_ocr_start = perf_total_start
        success_flag = True

        try:
            if self.stop_flag:
                return
            frame_with_roi = frame.copy()

            for idx, regions in enumerate(regions_list):
                ocr_results = []
                for (x, y, w, h) in regions:
                    roi = frame[y:y + h, x:x + w]
                    cv2.rectangle(frame_with_roi, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    if roi is None or roi.size == 0:
                        ocr_results.append("")
                        continue

                    try:
                        # 检查OCR模型是否已初始化
                        if self.ocr is None or not self.ocr_ready:
                            ocr_results.append("")
                            continue
                        
                        # 图像预处理 - 提高OCR识别准确率
                        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

                        result = self.ocr.ocr(thresh, cls=True)

                        if result and len(result) > 0 and isinstance(result[0], list):
                            detected_text = " ".join([line[1][0] for line in result[0] if line and len(line) > 1])
                        else:
                            detected_text = ""
                    except Exception as e:
                        print(f"OCR identifies anomalies: {e}")
                        detected_text = ""

                    ocr_results.append(detected_text)

                # 修正 Object 列的 OCR 常见错误：TRAIN1O -> TRAIN10
                if len(ocr_results) > 3 and ocr_results[3]:
                    ocr_results[3] = ocr_results[3].replace("TRAIN1O", "TRAIN10")

                # 仅在第五列文本非空时进行匹配
                if ocr_results[4]:
                    matched_text = self.match_text(ocr_results[4])
                    ocr_results[4] = matched_text
                else:
                    matched_text = ""

                if self.last_ocr_results[idx] == ocr_results:
                    continue
                self.last_ocr_results[idx] = ocr_results

                # 仅当第五列有文本时才显示和保存
                if ocr_results[4]:
                    self.display_ocr_results(ocr_results)
                    self.save_to_csv(ocr_results)
                    # --- 传完整五列数据 ---
                    self.check_alert_priority(ocr_results)

            # 更新左侧原始视频
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            qimg = QtGui.QImage(rgb_frame.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
            if not self.stop_flag:
                self.update_video_signal.emit(qimg.copy())

            # 更新右侧OCR标记画面
            frame_with_roi = frame.copy()
            for regions in regions_list:
                for (x, y, w, h) in regions:
                    cv2.rectangle(frame_with_roi, (x, y), (x + w, y + h), (0, 255, 0), 2)

            roi_rgb = cv2.cvtColor(frame_with_roi, cv2.COLOR_BGR2RGB)
            h2, w2, ch2 = roi_rgb.shape
            qimg2 = QtGui.QImage(roi_rgb.data, w2, h2, ch2 * w2, QtGui.QImage.Format_RGB888)
            self.update_ocr_signal.emit(qimg2.copy())
        except Exception:
            success_flag = False
            raise
        finally:
            total_ms = self.performance_monitor.stop_timer(perf_total_start)
            ocr_ms = self.performance_monitor.stop_timer(perf_ocr_start)
            # 统计本次OCR中所有区域的框数量，用于计算单位框耗时
            try:
                ocr_boxes = sum(len(regions) for regions in regions_list)
            except Exception:
                ocr_boxes = 1
            self.performance_monitor.record_metrics(
                ocr_ms=ocr_ms,
                total_ms=total_ms,
                success=success_flag,
                ocr_boxes=ocr_boxes,
            )


    # def display_ocr_results(self, ocr_results):
    #     row_count = self.ui.tableWidget_2.rowCount()
    #     self.ui.tableWidget_2.insertRow(row_count)
    #     for col, text in enumerate(ocr_results):
    #         self.ui.tableWidget_2.setItem(row_count, col, QtWidgets.QTableWidgetItem(text))
    #     # 添加自动滚动功能
    #     if self.auto_scroll_enabled:
    #         self.alarm_table.scrollToBottom()

    def display_ocr_results(self, ocr_results):
        row_count = self.ui.tableWidget_2.rowCount()
        self.ui.tableWidget_2.insertRow(row_count)
        for col, text in enumerate(ocr_results):
            self.ui.tableWidget_2.setItem(row_count, col, QtWidgets.QTableWidgetItem(text))

        # 更新 Action 列：根据优先级报警更新 Action 字段
        matched_text = ocr_results[4]  # 根据 OCR 结果获取文本
        if matched_text in self.alerts_priority:
            action_text = self.alerts_priority[matched_text].get("action", "无对应操作建议")
        else:
            action_text = "无对应操作建议"

        # 插入 Action 列的数据
        self.ui.tableWidget_2.setItem(row_count, 5, QtWidgets.QTableWidgetItem(action_text))

        # 添加自动滚动功能
        if self.auto_scroll_enabled:
            self.alarm_table.scrollToBottom()

    def init_csv(self):
        # 确保 output_data 文件夹存在
        output_folder = "output_data"
        os.makedirs(output_folder, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_name = f"alarmlist_ocr_results_{timestamp}.csv"
        csv_file_path = os.path.join(output_folder, file_name)

        if not self.csv_writer:
            self.csv_file = open(csv_file_path, mode='w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            if self.csv_file.tell() == 0:
                # 写 6 列表头（含 Action）
                self.csv_writer.writerow(["Date/Time", "Area", "Sub Area", "Object", "Text", "suggested Action"])
                print(f"CSV 文件已创建: {csv_file_path}")

    # def init_csv(self):
    #     # 确保 output_data 文件夹存在
    #     output_folder = "output_data"
    #     os.makedirs(output_folder, exist_ok=True)
    #
    #     # 创建带有 'alarmlist' 前缀的 CSV 文件
    #     timestamp = time.strftime("%Y%m%d_%H%M%S")
    #     file_name = f"alarmlist_ocr_results_{timestamp}.csv"  # 在文件名前添加 "alarmlist_"
    #
    #     # 拼接完整路径
    #     csv_file_path = os.path.join(output_folder, file_name)
    #
    #     if not self.csv_writer:
    #         self.csv_file = open(csv_file_path, mode='w', newline='', encoding='utf-8')
    #         self.csv_writer = csv.writer(self.csv_file)
    #         if self.csv_file.tell() == 0:
    #             # 写入表头
    #             self.csv_writer.writerow(["Date/Time", "Area", "Sub Area", "Object", "Text"])
    #
    #             print(f"CSV 文件已创建: {csv_file_path}")  # 确认文件创建成功

    def save_csv_periodically(self):
        if self.csv_writer:
            try:
                print("正在定期保存 CSV 数据。")
                self.csv_file.flush()  # 刷新缓冲区数据到文件
            except Exception as e:
                print(f"定期保存 CSV 出错: {e}")


    # def save_to_csv(self, ocr_results):
    #     if self.csv_writer:
    #         try:
    #             self.csv_writer.writerow(ocr_results)
    #         except Exception as e:
    #             print(f"Write to CSV exception: {e}")

    # 这个函数会不断向csv文件中更新，随时打开随时更新
    def save_to_csv(self, ocr_results):
        if self.csv_file:
            self.csv_writer.writerow(ocr_results)
            self.csv_file.flush()
                        
            # 【新增】同步推送到AI Assistant
            # 放宽条件：只要有数据就推送（即使某些字段为空）
            if push_alarmlist_data and ocr_results:
                try:
                    # 确保至少有6个字段，缺失的用空字符串填充
                    while len(ocr_results) < 6:
                        ocr_results.append("")
                    
                    push_alarmlist_data(
                        date_time=ocr_results[0] or "",
                        area=ocr_results[1] or "",
                        sub_area=ocr_results[2] or "",
                        object_name=ocr_results[3] or "",
                        text=ocr_results[4] or "",
                        suggested_action=ocr_results[5] or ""
                    )
                except Exception as e:
                    # 推送失败不影响主程序（但打印日志用于调试）
                    print(f"⚠ Alarm List推送失败: {e}")

    # ========== 文本匹配 & 优先级报警 ==========

    def match_text(self, detected_text):
        if not self.alerts_priority:
            return detected_text

        best_match = None
        highest_ratio = 0.0
        for item in self.alerts_priority.keys():
            ratio = difflib.SequenceMatcher(None, detected_text.lower(), item.lower()).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = item

        # 如果匹配度大于 0.6，就返回字典里的 key，否则返回原始 OCR 文本
        if best_match and highest_ratio > 0.6:
            print(f"Matched: '{detected_text}' -> '{best_match}' (ratio: {highest_ratio:.2f})")
            return best_match
        else:
            return detected_text

    def check_alert_priority(self, ocr_results):
        matched_text = ocr_results[4]

        if matched_text in self.alerts_priority:
            alert_info = self.alerts_priority[matched_text]
            priority = alert_info["priority"]
            action = alert_info.get("action", "无对应操作建议（待补充）")

            # 去重
            alert_key = tuple(ocr_results)
            if alert_key in self.last_alerts_sent:
                print(f"重复告警 {alert_key} 已检测过，跳过通知。")
                return
            self.last_alerts_sent.append(alert_key)

            # ✅ 永远输出操作建议
            print(f"🔔 Alert detected: '{matched_text}' (Priority: {priority})")
            print(f"👉 Suggested action: {action}")

            # ✅ 根据优先级触发不同通知
            if priority == 1:
                self.send_notification_auto(ocr_results)
                if not self.is_muted:
                    self.play_sound_alert_auto()
            elif priority == 2:
                self.send_email_auto(ocr_results)
            # 其余优先级仅显示 action，不触发通知

    # def check_alert_priority(self, ocr_results):
    #     matched_text = ocr_results[4]
    #
    #     if matched_text in self.alerts_priority:
    #         priority = self.alerts_priority[matched_text]
    #
    #         # --- 确认是有效告警，再做去重 ---
    #         alert_key = tuple(ocr_results)
    #         if alert_key in self.last_alerts_sent:
    #             print(f"重复告警 {alert_key} 已检测过，跳过通知。")
    #             return
    #
    #         self.last_alerts_sent.append(alert_key)
    #         print(f"添加新报警到历史: {alert_key} (当前数量: {len(self.last_alerts_sent)})")
    #         print(f"Alert detected: '{matched_text}' (Priority: {priority})")
    #
    #         if priority == 1:
    #             print("Triggering notification for priority 1 alert.")
    #             self.send_notification_auto(ocr_results)
    #             if not self.is_muted:
    #                 self.play_sound_alert_auto()
    #         elif priority == 2:
    #             print("Triggering email for priority 2 alert.")
    #             self.send_email_auto(ocr_results)

    def play_sound_alert_auto(self):
        try:
            winsound.Beep(1000, 500)
        except Exception as e:
            print(f"Error playing sound alert: {e}")

    def send_notification_auto(self, ocr_results):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        matched_text = ocr_results[4]
        # 从字典获取操作建议
        action_text = ""
        if matched_text in self.alerts_priority:
            action_text = self.alerts_priority[matched_text].get("action", "无对应操作建议（待补充）")

        message = (
            f"⚠️ High Priority Alert Detected!\n"
            f"Time: {timestamp}\n"
            f"Date/Time: {ocr_results[0]}\n"
            f"Area: {ocr_results[1]}\n"
            f"Sub Area: {ocr_results[2]}\n"
            f"Object: {ocr_results[3]}\n"
            f"Text: {ocr_results[4]}\n"
            f"Action: {action_text}"
        )

        webhook_url = self.settings.get("WeChat Webhook URL")
        if not webhook_url:
            print("WeChat Webhook URL not configured. Skipping notification.")
            return

        payload = {"msgtype": "text", "text": {"content": message}}

        print(f"Sending WeChat notification for: {ocr_results[4]}")
        try:
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 200:
                print("✅ WeChat notification sent successfully.")
            else:
                print(f" Failed to send WeChat notification. Status code: {response.status_code}")
                print(f"Response content: {response.text}")
        except Exception as e:
            print(f"Error sending WeChat notification: {e}")

    # def send_notification_auto(self, ocr_results):
    #     timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    #
    #     message = (
    #         f"High Priority Alert Detected!\n"
    #         f"Time: {timestamp}\n"
    #         f"Date/Time: {ocr_results[0]}\n"
    #         f"Area: {ocr_results[1]}\n"
    #         f"Sub Area: {ocr_results[2]}\n"
    #         f"Object: {ocr_results[3]}\n"
    #         f"Text: {ocr_results[4]}"
    #     )
    #
    #     webhook_url = self.settings.get("WeChat Webhook URL")
    #     if not webhook_url:
    #         print("WeChat Webhook URL not configured. Skipping notification.")
    #         return
    #
    #     payload = {"msgtype": "text", "text": {"content": message}}
    #
    #     print(f"Sending WeChat notification for: {ocr_results[4]}")
    #     try:
    #         response = requests.post(webhook_url, json=payload)
    #         if response.status_code == 200:
    #             print("WeChat notification sent successfully.")
    #         else:
    #             print(f"Failed to send WeChat notification. Status code: {response.status_code}")
    #             print(f"Response content: {response.text}")
    #     except Exception as e:
    #         print(f"Error sending WeChat notification: {e}")

    def send_email_auto(self, ocr_results):
        receiver_email = self.settings.get("Receiver Email")
        smtp_server = self.settings.get("Smtp server")
        smtp_port = int(self.settings.get("Smtp port"))
        sender_email = self.settings.get("Sender email")
        sender_password = self.settings.get("Sender password")

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        matched_text = ocr_results[4]
        action_text = ""
        if matched_text in self.alerts_priority:
            action_text = self.alerts_priority[matched_text].get("action", "无对应操作建议（待补充）")

        subject = f"⚠️ Medium Priority Alert Detected - {timestamp}"
        body = (
            f"The following Alarmlist results were detected (Timestamp: {timestamp}):\n\n"
            f"Date/Time: {ocr_results[0]}\n"
            f"Area: {ocr_results[1]}\n"
            f"Sub Area: {ocr_results[2]}\n"
            f"Object: {ocr_results[3]}\n"
            f"Text: {ocr_results[4]}\n"
            f"Action: {action_text}\n\n"
            f"Alert Priority: 2 (Medium)"
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
            print(" Email notification sent automatically.")
        except Exception as e:
            print(f" Error sending email notification: {e}")


    def convertCvToPixmap(self, cv_img):
        """
        将 OpenCV 图像转换为 QPixmap 对象，用于在 PyQt 界面上显示。
        """
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        return QtGui.QPixmap.fromImage(QtGui.QImage(
            cv_img.data, w, h, bytes_per_line, QtGui.QImage.Format_BGR888))

    def close_all(self):
        """
        释放摄像头资源和关闭 CSV 文件，同时在退出时补齐性能日志。
        """
        try:
            self.stop_detection()
        except Exception as e:
            print(f"关闭告警检测时出现异常: {e}")

        if self.cap:
            self.cap.release()
            self.cap = None
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None