import sys
import os
import cv2
import csv
import datetime
import time
import requests
import smtplib
import winsound
import numpy as np

# 导入实时推送模块
try:
    from realtime_push import push_power_data
except ImportError:
    push_power_data = None
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer, Qt, QEvent, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QAbstractItemView, QTableWidgetItem, QMessageBox
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from paddleocr import PaddleOCR
from performance_monitor import PerformanceMonitor


# OCR 线程
class OCRThread(QtCore.QThread):
    result_signal = pyqtSignal(list, object)  # 用于传递OCR结果的信号

    def __init__(self, ocr_instance, frame, regions_list):
        super().__init__()
        self.ocr_instance = ocr_instance
        self.frame = frame
        self.regions_list = regions_list

    def run(self):
        """
        线程的入口方法。进行OCR处理，识别图像中的文字，并将结果传递给主线程。
        """
        try:
            ocr_results = self.process_ocr(self.frame, self.regions_list)
            self.result_signal.emit(ocr_results, self.frame)
        except Exception as e:
            print(f"OCR线程错误: {e}")

    def process_ocr(self, frame, regions_list):
        """
        OCR识别处理逻辑
        """
        ocr_results = []
        # 进行OCR检测
        for regions in regions_list:
            result = self.ocr_instance.ocr(frame, cls=True)
            ocr_results.append(result)
        return ocr_results


class PowerIntegration(QtCore.QObject):
    """
    将 Power.txt 中的所有逻辑整合到此类
    """

    update_video_signal = pyqtSignal(QtGui.QImage)
    update_ocr_signal = pyqtSignal(QtGui.QImage)

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.auto_scroll_enabled = True  # 添加自动滚动标志

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

        self.ocr_busy = False

        # 设置 frame_25、frame_24 样式
        self.ui.frame_25.setStyleSheet("border-radius:0px; background-color:#2f5597;")
        self.ui.frame_24.setStyleSheet("border-radius:0px; background-color:#2f5597;")

        # 在 frame_25、frame_24 中添加 QLabel 用于显示画面
        self.videoLabel = QLabel()
        self.videoLabel.setScaledContents(True)
        layout25 = QVBoxLayout(self.ui.frame_25)
        layout25.setContentsMargins(0, 0, 0, 0)
        layout25.addWidget(self.videoLabel)

        self.ocrLabel = QLabel()
        self.ocrLabel.setScaledContents(True)
        layout24 = QVBoxLayout(self.ui.frame_24)
        layout24.setContentsMargins(0, 0, 0, 0)
        layout24.addWidget(self.ocrLabel)

        # 初始化表格
        self.table = self.ui.tableWidget_5
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date/Time", "ID", "Description", "Status"])
        self.table.setRowCount(0)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # 关联按钮
        self.ui.pushButton_46.clicked.connect(self.start_detection)
        self.ui.pushButton_47.clicked.connect(self.reset_detection_region)
        self.ui.pushButton_48.clicked.connect(self.cancel_last_selection)
        self.ui.pushButton_49.clicked.connect(self.stop_detection)
        self.ui.pushButton_50.clicked.connect(self.send_notification)
        self.ui.pushButton_51.clicked.connect(self.send_email)
        self.ui.pushButton_52.clicked.connect(self.play_sound_alert)
        self.ui.pushButton_53.clicked.connect(self.set_wechat_webhook_url)
        self.ui.pushButton_54.clicked.connect(self.set_receiver_email)
        self.ui.pushButton_55.clicked.connect(self.set_smtp_settings)

        # 其余参数
        self.cap = None
        self.is_running = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.capture_frame)
        self.video_started = False
        self.frame_skip = 10  # GPU优化：10帧跳帧，约0.3-0.4秒检测一次（平衡实时性和性能）
        self.frame_count = 0
        self.performance_monitor = PerformanceMonitor(
            module_name="Power Detection",
            log_dir=os.path.join("performance_logs", "power"),
        )

        self.csv_writer = None
        self.csv_file = None

        # OCR初始化 - 明确启用GPU加速
        self.ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=True)

        self.keywords = {
            "PS", "PS-T", "PS-P", "PS-S", "EL", "MSA", "MSB", "MSA-F",
            "MSB-F", "LOAD", "BATT", "BAT-U", "BAT-O", "BYP", "M-BYP",
            "FAN", "UPS", "TEMP", "MBKF"
        }

        self.description_map = {
            "PS": "Power supply panel",
            "PS-T": "Power supply track circuits",
            "PS-P": "Power supply points",
            "PS-S": "Power supply signals",
            "EL": "Earth leakage",
            "MSA": "Main supply A available",
            "MSB": "Main supply B available",
            "MSA-F": "Main supply A feeding",
            "MSB-F": "Main supply B feeding",
            "LOAD": "Load on inverter / bypass",
            "BATT": "Battery",
            "BAT-U": "Battery undervoltage",
            "BAT-O": "Battery operation",
            "BYP": "Bypass operation (single point operation)",
            "M-BYP": "Manual bypass",
            "FAN": "Fan",
            "UPS": "UPS",
            "TEMP": "Overtemperature alarm",
            "MBKF": "Main Backup Feeding"
        }

        # 存储手动选区
        self.manual_partitions = []
        self.is_selecting = False
        self.start_x = self.start_y = self.end_x = self.end_y = 0

        # 在 videoLabel 上安装事件过滤器，用于鼠标选区
        self.videoLabel.installEventFilter(self)

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

    def set_station(self, station: str):
        self.current_station = station
        print(f"电源（Power）模块的站点已设置为: {self.current_station}")

    # Setting Functions
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

    def eventFilter(self, obj, event):
        if obj is self.videoLabel:
            # 鼠标按下事件 - 开始选择区域
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self.is_selecting = True
                self.start_x = event.x()
                self.start_y = event.y()
                self.end_x = self.start_x
                self.end_y = self.start_y
                return True

            # 鼠标移动事件 - 更新选择区域
            elif event.type() == QEvent.MouseMove and self.is_selecting:
                self.end_x = event.x()
                self.end_y = event.y()
                self.videoLabel.update()  # 触发重绘以显示选择框
                return True

            # 鼠标释放事件 - 完成选择区域
            elif event.type() == QEvent.MouseButtonRelease and self.is_selecting and event.button() == Qt.LeftButton:
                self.is_selecting = False
                x0 = min(self.start_x, self.end_x)
                x1 = max(self.start_x, self.end_x)
                y0 = min(self.start_y, self.end_y)
                y1 = max(self.start_y, self.end_y)
                if x1 - x0 > 1 and y1 - y0 > 1:
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
                painter.setBrush(QColor(255, 0, 0, 50))  # 红色半透明填充
                painter.drawRect(rx, ry, rw, rh)
                return False

        return super().eventFilter(obj, event)

    def start_detection(self):
        if self.video_started:
            return
        self.init_csv_once()
        try:
            camera_index_str = self.ui.comboBox_33.currentText()
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

        self.video_started = True
        self.is_running = True
        self.frame_count = 0
        self.performance_monitor.start_run()

        self.ui.pushButton_46.setEnabled(False)
        self.ui.pushButton_49.setEnabled(True)

        # 清除暂停状态显示
        self.videoLabel.setText("")
        self.videoLabel.setStyleSheet("")

        # 创建或重新启动定时器
        if not hasattr(self, 'timer'):
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.capture_frame)

        self.timer.start(30)

        # 定时保存 CSV
        self.periodic_csv_timer = QTimer()
        self.periodic_csv_timer.timeout.connect(self.save_csv_periodically)
        self.periodic_csv_timer.start(30000)  # 每 30 秒保存一次

    def stop_detection(self):
        """暂停检测但不释放摄像头资源"""
        self.is_running = False

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

        self.video_started = False
        self.ui.pushButton_46.setEnabled(True)
        self.ui.pushButton_49.setEnabled(False)

        if hasattr(self, 'videoLabel'):
            self.videoLabel.setText("检测已暂停")
            self.videoLabel.setStyleSheet(
                """ QLabel { font-size: 16px; color: #666; background: #f0f0f0; border: 1px solid #ddd; } """)
            self.videoLabel.setAlignment(Qt.AlignCenter)

    def reset_detection_region(self):
        self.manual_partitions.clear()
        self.videoLabel.update()

    def cancel_last_selection(self):
        if self.manual_partitions:
            self.manual_partitions.pop()
        self.videoLabel.update()

    def init_csv_once(self):
        output_folder = "output_data"
        os.makedirs(output_folder, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        csv_file_path = os.path.join(output_folder, f"power_ocr_results_{timestamp}.csv")

        if not self.csv_writer:
            self.csv_file = open(csv_file_path, mode="a", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            if self.csv_file.tell() == 0:
                self.csv_writer.writerow(["Date/Time", "ID", "Description", "Status"])

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

    def capture_frame(self):
        if not self.cap or not self.is_running:
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
        self.frame_count += 1
        if self.frame_count % self.frame_skip != 0:
            self.update_video_label(frame)
            return

        perf_total_start = self.performance_monitor.start_timer()
        perf_ocr_start = None
        ocr_ms = None
        success_flag = True
        try:
            perf_ocr_start = self.performance_monitor.start_timer()
            processed_frame = self.perform_ocr_and_color(frame)
            ocr_ms = self.performance_monitor.stop_timer(perf_ocr_start)
            self.update_video_label(frame)
            self.update_ocr_label(processed_frame)
        except Exception:
            success_flag = False
            # 异常分支：如果已 start 但未 stop，需补 stop 防止悬空计时
            if perf_ocr_start is not None and ocr_ms is None:
                ocr_ms = self.performance_monitor.stop_timer(perf_ocr_start)
            raise
        finally:
            total_ms = self.performance_monitor.stop_timer(perf_total_start)
            self.performance_monitor.record_metrics(
                ocr_ms=ocr_ms,
                total_ms=total_ms,
                success=success_flag
            )

    def update_video_label(self, cv_img):
        qpix = self.cv_to_qpixmap(cv_img)
        self.videoLabel.setPixmap(qpix.scaled(
            self.videoLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def update_ocr_label(self, cv_img):
        qpix = self.cv_to_qpixmap(cv_img)
        self.ocrLabel.setPixmap(qpix.scaled(
            self.ocrLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def perform_ocr_and_color(self, cv_img):
        if cv_img is None or cv_img.size == 0:
            return cv_img
        annotated = cv_img.copy()

        # --- 新增：识别时间戳 ---
        timestamp_x0, timestamp_y0, timestamp_x1, timestamp_y1 = 1781, 75, 1903, 107
        timestamp_region = cv_img[timestamp_y0:timestamp_y1, timestamp_x0:timestamp_x1]
        timestamp_text = self.performOCRForTimestamp(timestamp_region)

        h, w = cv_img.shape[:2]
        label_w = self.videoLabel.width()
        label_h = self.videoLabel.height()

        for (sx, sy, ex, ey) in self.manual_partitions:
            if label_w == 0 or label_h == 0:
                continue
            x0 = int(sx * w / label_w)
            y0 = int(sy * h / label_h)
            x1 = int(ex * w / label_w)
            y1 = int(ey * h / label_h)

            if x0 < 0: x0 = 0
            if y0 < 0: y0 = 0
            if x1 > w: x1 = w
            if y1 > h: y1 = h

            cv2.rectangle(annotated, (x0, y0), (x1, y1), (0, 0, 255), 2)
            roi = cv_img[y0:y1, x0:x1]
            result = self.ocr.ocr(roi, cls=True)

            detected_contents = []
            if result:
                for line in result:
                    if line and isinstance(line, list):
                        for det in line:
                            text = det[1][0]
                            if text in self.keywords:
                                points = np.array(det[0]).astype(int)
                                min_x = np.min(points[:, 0])
                                min_y = np.min(points[:, 1])
                                max_x = np.max(points[:, 0])
                                max_y = np.max(points[:, 1])
                                abs_min_x = x0 + min_x
                                abs_min_y = y0 + min_y
                                abs_max_x = x0 + max_x
                                abs_max_y = y0 + max_y
                                cv2.rectangle(annotated, (abs_min_x, abs_min_y), (abs_max_x, abs_max_y), (0, 255, 0), 2)

                                text_region = roi[min_y:max_y, min_x:max_x]
                                color_str = self.get_text_color(text_region)
                                detected_contents.append((text, color_str))

            # --- 修改：传入 timestamp_text ---
            self.displayMatchingContents(detected_contents, timestamp_text)

        return annotated

    def get_text_color(self, region):
        if region is None or region.size == 0:
            return "gray"
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
        elif avg_color[2] > avg_color[1] and avg_color[1] > avg_color[0]:
            return "orange"
        else:
            return "gray"

    def displayMatchingContents(self, contents, timestamp_text=None):
        if not contents:
            return

        if not timestamp_text:
            timestamp_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for (text, color) in contents:
            description = self.description_map.get(text, "Unknown")
            status = self.infer_status(text, color)

            row_count = self.table.rowCount()
            self.table.insertRow(row_count)
            self.table.setItem(row_count, 0, QTableWidgetItem(timestamp_text))
            self.table.setItem(row_count, 1, QTableWidgetItem(text))
            self.table.setItem(row_count, 2, QTableWidgetItem(description))
            self.table.setItem(row_count, 3, QTableWidgetItem(status))

            self.save_csv_line(timestamp_text, text, description, status)

        if self.auto_scroll_enabled:
            self.table.scrollToBottom()

    def performOCRForTimestamp(self, region):
        try:
            result = self.ocr.ocr(region, cls=True)
            if (
                    result and isinstance(result, list) and len(result) > 0 and
                    isinstance(result[0], list) and len(result[0]) > 0 and
                    isinstance(result[0][0], (list, tuple)) and len(result[0][0]) > 1 and
                    isinstance(result[0][0][1], (list, tuple)) and len(result[0][0][1]) > 0
            ):
                return result[0][0][1][0]
        except:
            pass
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def infer_status(self, text, color):
        # 完整保留 power.txt 中的 if-else
        if text == "PS":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Panel okay"
            elif color == "red":
                return "Panel not okay"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "PS-T":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Okay"
            elif color == "red":
                return "Not okay"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "PS-P":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Okay"
            elif color == "red":
                return "Not okay"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "PS-S":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Okay"
            elif color == "red":
                return "Not okay"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "EL":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "No Earth Leakage"
            elif color == "red":
                return "Earth leakage detected"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "MSA":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Mains A available"
            elif color == "red":
                return "Mains A not available"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "MSB":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Mains B available"
            elif color == "red":
                return "Mains B not available"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "MSA-F":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Mains A feeding"
            elif color == "blue":
                return "Mains A not feeding"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "MSB-F":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Mains B feeding"
            elif color == "blue":
                return "Mains B not feeding"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "LOAD":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Load on inverter"
            elif color == "red":
                return "Load on bypass"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "BATT":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Battery okay"
            elif color == "red":
                return "Battery not okay"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "BAT-U":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Battery Voltage okay"
            elif color == "red":
                return "Battery undervoltage"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "BAT-O":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Battery not in operation"
            elif color == "red":
                return "Battery operation"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "BYP":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Bypass not in Operation"
            elif color == "red":
                return "Bypass in Operation"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "M-BYP":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Manual Bypass not active"
            elif color == "red":
                return "Manual Bypass active"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "FAN":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Okay"
            elif color == "red":
                return "Not okay"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "UPS":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "UPS is okay"
            elif color == "red":
                return "UPS disturbed"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "TEMP":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Temperature okay"
            elif color == "red":
                return "Overtemperature"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        elif text == "MBKF":
            if color == "gray":
                return "No data available"
            elif color == "green":
                return "Backup Mains feeding"
            elif color == "blue":
                return "Backup Mains not feeding"
            elif color == "orange":
                return "Discrepancy"
            else:
                return "Unknown"
        else:
            return "Unknown"


    # def save_csv_line(self, dt, id_, desc, status):
    #     if self.csv_file:
    #         try:
    #             self.csv_writer.writerow([dt, id_, desc, status])
    #         except Exception as e:
    #             print(f"Write to CSV exception: {e}")

    # 这个函数会不断向csv文件中更新，随时打开随时更新
    def save_csv_line(self, dt, id_, desc, status):
        if self.csv_file:
            self.csv_writer.writerow([dt, id_, desc, status])
            self.csv_file.flush()
                        
            # 【新增】同步推送到AI Assistant  
            if push_power_data:
                try:
                    push_power_data(dt, id_, desc, status)
                except:
                    pass

    def send_notification(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to send a notification.")
            return
        data = []
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            data.append(item.text() if item else "")

        message = f"Date/Time: {data[0]}\nID: {data[1]}\nDescription: {data[2]}\nStatus: {data[3]}"

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
            resp = requests.post(webhook_url, json=payload)
            if resp.status_code == 200:
                QMessageBox.information(None, "Notification", "The notification was sent successfully.")
            else:
                QMessageBox.warning(None, "Error", f"Failed to send notification. Status code: {resp.status_code}")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"An error occurred while sending the notification: {e}")

    def send_email(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to send an email.")
            return
        data = []
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            data.append(item.text() if item else "")

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
            f"The following Power results were detected (Timestamp: {timestamp}):\n\n"
            f"Date/Time: {data[0]}\n"
            f"ID: {data[1]}\n"
            f"Description: {data[2]}\n"
            f"Status: {data[3]}\n"
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

    def play_sound_alert(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to play the sound alert.")
            return
        try:
            winsound.Beep(1000, 500)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to play sound: {e}")

    def cv_to_qpixmap(self, cv_img):
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        return QtGui.QPixmap.fromImage(QtGui.QImage(
            cv_img.data, w, h, bytes_per_line, QtGui.QImage.Format_BGR888
        ))

    def close_all(self):
        try:
            self.stop_detection()
        except Exception as e:
            print(f"关闭电力检测时出现异常: {e}")

        if self.cap:
            self.cap.release()
            self.cap = None
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
