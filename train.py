import sys
import os
import re
import cv2
import csv
import ast
import datetime
import time
import requests
import numpy as np
import smtplib
import winsound

# 导入实时推送模块
try:
    from realtime_push import push_train_data, push_route_check_data
except ImportError:
    push_train_data = None
    push_route_check_data = None
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer, QEvent, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import (
    QTableWidgetItem, QMessageBox, QVBoxLayout, QLabel, QWidget, QAbstractItemView
)
from paddleocr import PaddleOCR
from collections import defaultdict
from performance_monitor import PerformanceMonitor


# ---------------------- 信号灯类 ----------------------
class StationConfigLoader:
    def __init__(self, config_folder="station_configs"):
        self.config_folder = config_folder
        os.makedirs(self.config_folder, exist_ok=True)
        self.initialize_default_configs()

    def initialize_default_configs(self):
        """创建默认的配置文件（如果不存在）"""
        default_configs = {
            "LOW": {
                "signal_id_position_setting": (
                    "2453,(92,996,106,1008);2536,(547,814,560,826);2502,(547,903,560,918);2501,(897,814,910,827);"
                    "2533,(898,906,912,916);801,(387,724,402,735);804,(573,724,588,735);802,(572,634,587,645);"
                    "809,(811,633,839,645);818,(824,632,840,647);811,(810,723,824,736);820,(827,724,839,735);"
                    "825,(1063,633,1076,645);827,(1064,723,1077,735);832,(1250,687,1265,700);2753,(1258,723,1273,736);"
                    "2542,(1448,724,1459,739);2540,(1445,837,1456,849);2510,(1449,927,1463,940);2509,(1678,724,1691,734);"
                    "2505,(1675,837,1689,848);2546,(1764,723,1775,735);2514,(1764,837,1775,848);SB,(1869,725,1881,735);"
                    "SA,(1867,835,1882,849);ceshi,(827,421,914,498)"
                ),
                "regions": {
                    1: (1549, 791, 1578, 811),
                    2: (1554, 828, 1582, 848),
                    3: (1551, 878, 1581, 902),
                    4: (1554, 918, 1579, 937)
                },
                "dwell_time_regions": {
                    (1, 2): (572, 600, 1490, 1550),
                    (3, 4): (600, 632, 1490, 1550)
                },
                "station_region": (500, 548, 1500, 1635)
            },
            "SHS": {
                "signal_id_position_setting": (
                    "2344,(73,701,84,716);2312,(73,842,86,857);2403,(149,700,162,715);2431,(146,843,161,857);"
                    "2430,(478,700,495,714);2402,(476,842,490,857);2407,(720,700,733,714);2411,(722,842,736,857);"
                    "2436,(1110,297,1127,310);2409,(1112,415,1129,430);2406,(1110,843,1125,855);2412,(1205,964,1223,978);"
                    "2438,(1278,700,1294,714);2411,(1401,700,1418,715);2449,(1404,841,1416,855);2442,(1717,700,1732,714);"
                    "2416,(1718,841,1732,855);2479,(1644,953,1659,969);2420,(1727,926,1742,938);ceshi,(827,421,914,498)"
                ),
                "regions": {
                    1: (580, 675, 616, 703),
                    2: (583, 834, 619, 857)
                },
                "dwell_time_regions": {
                    1: (569, 588, 516, 570),
                    2: (590, 607, 515, 569)
                },
                "station_region": (477, 735, 463, 735),
                "route_check_regions": {
                    "SHS": (713, 711, 1081, 730),
                    "LMC": (1117, 433, 1146, 687),
                    "LOW": (1127, 710, 1726, 732)
                }
            }
        }

        for station, config in default_configs.items():
            config_file = os.path.join(self.config_folder, f"{station}.csv")
            if not os.path.exists(config_file):
                self.save_config_to_file(station, config)

    def save_config_to_file(self, station, config):
        """将配置保存到CSV文件"""
        config_file = os.path.join(self.config_folder, f"{station}.csv")
        with open(config_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["key", "value"])
            for key, value in config.items():
                # 将列表和字典转换为字符串表示
                if isinstance(value, (list, dict)):
                    value_str = str(value)
                else:
                    value_str = value
                writer.writerow([key, value_str])

    def load_config(self, station):
        """从CSV文件加载配置"""
        config_file = os.path.join(self.config_folder, f"{station}.csv")
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file for station {station} not found")

        config = {}
        with open(config_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # 跳过标题行
            for row in reader:
                if len(row) >= 2:
                    key = row[0].strip()
                    value_str = row[1].strip()

                    # 尝试将字符串转换为Python对象（列表或字典）
                    try:
                        value = ast.literal_eval(value_str)
                    except (ValueError, SyntaxError):
                        value = value_str

                    config[key] = value

        # 验证必要参数是否存在
        required_keys = ["signal_id_position_setting", "regions", "dwell_time_regions", "station_region"]
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")

        # route_check_regions是可选参数，不验证

        return config


class SignalLight:
    def __init__(self, sid, coords):
        self.id = sid
        self.x1, self.y1, self.x2, self.y2 = coords
        self.color = "unknown"
        self.center = ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)


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


class TrainIntegration(QObject):
    update_video_signal = pyqtSignal(QtGui.QImage)  # 用于更新视频显示
    update_ocr_signal = pyqtSignal(QtGui.QImage)  # 用于更新 OCR 结果显示

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.auto_scroll_enabled = True
        self.config_loader = StationConfigLoader()  # 初始化配置加载器

        self.last_frame = None  # <<< 新增：缓存最近一帧，供信号灯颜色更新使用

        # 初始化 signal_table
        self.signal_table = self.ui.tableWidget_6
        self.signal_table.setColumnCount(3)
        self.signal_table.setHorizontalHeaderLabels(["Train", "Signal ID", "Color"])
        self.signal_table.setRowCount(0)
        self.signal_table.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.signal_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)

        # 初始化当前站点，默认 LOW
        self.current_station = "LOW"
        self.load_station_config(self.current_station)  # 加载初始配置

        # 添加车站名称映射
        self.station_name_mapping = {
            "LOW": "Lo Wu",
            "SHS": "Sheung Shui",
            "UNI": "University",
            "MKK": "Mong KoK East",
            "ADM": "Admiralty",
            "EXC": "Exhibition Centre",
            "FAN": "Fanling",
            "FOT": "Fo Tan",
            "KOT": "Kowloon Tong",
            "LMC": "Lok Ma Chau",
            "NHUH": "New Hung Hom",
            "RAC": "Racecourse",
            "SHT": "Sha Tin",
            "TAP": "Tai Po Market",
            "TAW": "Tai Wai",
            "TWO": "Tai Wo",
            "HUH": "Hung Hom Station",
        }

        # 现在可以安全调用 create_signal_lights
        # self.signal_config = self.create_signal_lights()
        self.signal_lights = self.create_signal_lights()
        self.previous_route_rows = {}  # 缓存上一次检测到的路线结果（按 train_id）
        self.route_alarm_sent = {}  # 跟踪每个列车是否已发送进路排列错误报警

        # 其他设置变量
        self.settings = self.load_settings_from_csv("default account.csv")
        self.abnormal_dwell_time_setting = 20
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

        # 初始化界面控件
        self.spadMonitor = self.ui.tableWidget_7
        self.spadMonitor.setRowCount(2)
        self.spadMonitor.setColumnCount(1)
        self.spadMonitor.setVerticalHeaderLabels(["Status", "Coordinates"])
        self.spadMonitor.setHorizontalHeaderLabels(["Value"])
        self.spadMonitor.horizontalHeader().setVisible(False)
        self.spadMonitor.setItem(0, 0, QTableWidgetItem("Normal"))
        self.spadMonitor.setItem(1, 0, QTableWidgetItem("Waiting..."))

        self.ui.frame_22.setStyleSheet("border-radius:0px; background-color:#2f5597;")
        self.ui.frame_23.setStyleSheet("border-radius:0px; background-color:#2f5597;")
        # OCR初始化 - 明确启用GPU加速
        self.ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=True)

        self.videoLabel = QLabel()
        self.videoLabel.setScaledContents(True)
        self.videoLabel.setMouseTracking(True)
        self.videoLabel.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.videoLabel.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.videoLabel.installEventFilter(self)
        layout22 = QVBoxLayout(self.ui.frame_22)
        layout22.setContentsMargins(0, 0, 0, 0)
        layout22.addWidget(self.videoLabel)

        self.ocrLabel = QLabel()
        self.ocrLabel.setScaledContents(True)
        layout23 = QVBoxLayout(self.ui.frame_23)
        layout23.setContentsMargins(0, 0, 0, 0)
        layout23.addWidget(self.ocrLabel)

        self.trainTable = self.ui.tableWidget_4
        self.trainTable.setColumnCount(8)
        self.trainTable.setHorizontalHeaderLabels(
            ["Train ID", "Date/Time", "Status", "Delay", "Dwell Time", "Location", "Station", "Door"])
        self.trainTable.setRowCount(0)
        self.trainTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trainTable.setSelectionMode(QAbstractItemView.SingleSelection)

        # 按钮连接
        self.ui.pushButton_39.clicked.connect(self.startVideoStream)
        self.ui.pushButton_40.clicked.connect(self.resetDetectionRegion)
        self.ui.pushButton_41.clicked.connect(self.cancelLastSelection)
        self.ui.pushButton_42.clicked.connect(self.stop_detection)
        self.ui.pushButton_43.clicked.connect(self.send_notification)
        self.ui.pushButton_44.clicked.connect(self.send_email)
        self.ui.pushButton_45.clicked.connect(self.play_sound_alert)
        self.ui.pushButton_16.clicked.connect(self.associate_items)
        self.ui.pushButton_17.clicked.connect(self.cancel_association)
        self.ui.pushButton_18.clicked.connect(self.start_spad_detection)

        self.ui.pushButton_29.clicked.connect(self.set_train_ids)
        self.ui.pushButton_31.clicked.connect(self.set_signal_id_position)
        self.ui.pushButton_53.clicked.connect(self.set_wechat_webhook_url)
        self.ui.pushButton_54.clicked.connect(self.set_receiver_email)
        self.ui.pushButton_56.clicked.connect(self.set_abnormal_dwell_time)
        self.ui.pushButton_55.clicked.connect(self.set_smtp_settings)

        # 其他属性
        self.manual_partitions = []
        self.is_selecting = False
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.video_started = False
        self.cap = None
        self.is_running = False
        self.frame_count = 0
        self.frame_skip = 10  # GPU优化：10帧跳帧，约0.3-0.4秒检测一次（平衡实时性和性能）
        self.frame_width = 0
        self.frame_height = 0
        self.current_camera_index = None  # 记录当前使用的摄像头索引
        self.csv_file = None
        self.csv_writer = None
        self.route_csv_file = None
        self.route_csv_writer = None
        self.detected_train_ids = set()
        self.conversion_time_diffs = []
        self.last_conversion_time = None
        self.previous_status = None
        self.previous_colors = {}
        self.reverse_start_time = None
        self.last_status = None
        # self.keywords = set(self.train_ids_setting.split(','))
        self.train_positions = {}
        self.associated_train = None
        self.associated_signal = None
        self.spad_detected = False
        self.train_crossing_status = {}
        self.previous_train_status = {}
        self.signal_timer = QTimer()
        self.signal_timer.timeout.connect(self.update_signal_colors)
        self.performance_monitor = PerformanceMonitor(
            module_name="Train Detection",
            log_dir=os.path.join("performance_logs", "train"),
        )

    def route_recall_detection(self, cv_img, train_id):
        if self.current_station != "SHS":
            return

        # 从配置文件读取区域坐标
        if not hasattr(self, 'route_check_regions') or not self.route_check_regions:
            print("警告: 未找到进路检查区域配置，使用默认值")
            area2 = (713, 711, 1081, 730)  # SHS
            area3 = (1117, 433, 1146, 687)  # LMC
            area4 = (1127, 710, 1726, 732)  # LOW
        else:
            area2 = self.route_check_regions.get("SHS", (713, 711, 1081, 730))
            area3 = self.route_check_regions.get("LMC", (1117, 433, 1146, 687))
            area4 = self.route_check_regions.get("LOW", (1127, 710, 1726, 732))

        def is_green(region):
            if region.size == 0:
                return False
            hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            lower = np.array([35, 50, 50])
            upper = np.array([85, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
            return cv2.countNonZero(mask) > 500

        # ROI
        roi2 = cv_img[area2[1]:area2[3], area2[0]:area2[2]]
        roi3 = cv_img[area3[1]:area3[3], area3[0]:area3[2]]
        roi4 = cv_img[area4[1]:area4[3], area4[0]:area4[2]]

        green2 = is_green(roi2)
        green3 = is_green(roi3)
        green4 = is_green(roi4)

        # 检查第二个字母（索引为1）来确定列车类型
        # 第一个字母可能变动，但第二个字母L表示去LMC，M表示去LOW
        second_letter = train_id[1] if len(train_id) >= 2 else ""

        # 列车类型
        if second_letter == "L":
            train_type = f"{train_id} (to LMC)"
        elif second_letter == "M":
            train_type = f"{train_id} (to LOW)"
        else:
            train_type = train_id

        #  按照表格
        result = "Other"

        # ---- 第二个字母为L (To LMC) ----
        if second_letter == "L":
            # L pass
            if green2 and green3 and not green4:
                result = "Pass"
            # L fail
            elif green2 and (not green3) and green4:
                result = "Fail"

        # ---- 第二个字母为M (To LOW) ----
        elif second_letter == "M":
            # M pass
            if green2 and (not green3) and green4:
                result = "Pass"
            # M fail
            elif green2 and green3 and not green4:
                result = "Fail"

        # 更新 UI
        row = 0
        self.ui.tableWidget_8.setItem(row, 1, QTableWidgetItem(train_type))
        self.ui.tableWidget_8.setItem(row, 3, QTableWidgetItem("Green" if green2 else "Not Green"))
        self.ui.tableWidget_8.setItem(row, 5, QTableWidgetItem("Green" if green3 else "Not Green"))
        self.ui.tableWidget_8.setItem(row, 7, QTableWidgetItem("Green" if green4 else "Not Green"))

        result_item = QTableWidgetItem(result)
        if result == "Pass":
            result_item.setForeground(QtGui.QBrush(QtGui.QColor("green")))
        else:
            result_item.setForeground(QtGui.QBrush(QtGui.QColor("red")))
        self.ui.tableWidget_8.setItem(row, 9, result_item)

        # === 存储 + 通知 ===
        timestamp_text = self.performOCRForTimestamp(
            cv_img[75:107, 1781:1903]  # 右上角区域
        )

        shs_result = "Green" if green2 else "Not Green"
        lmc_result = "Green" if green3 else "Not Green"
        low_result = "Green" if green4 else "Not Green"

        # 存储到 CSV （文件名还是按当天日期）
        self.save_route_check_to_csv(timestamp_text, train_type, shs_result, lmc_result, low_result, result)

        # # 如果错误 → 发通知
        # if result == "Fail":
        #     self.send_notification_auto(
        #         train_id, timestamp_text, "Route Check", "", "", "", self.current_station, f"Route {result}"
        #     )
        # === 存储当前帧行数据并对比前一帧 ===
        current_row = {
            "Train ID Type": train_type,
            "SHS": shs_result,
            "LMC": lmc_result,
            "LOW": low_result,
            "Result": result
        }
        prev_row = self.previous_route_rows.get(train_type)
        self.previous_route_rows[train_type] = current_row  # 更新缓存

        # 进路排列错误报警逻辑：同一列车只发送一次报警通知
        if result == "Fail":
            # 检查该列车是否已经发送过报警
            if not self.route_alarm_sent.get(train_type, False):
                # 首次检测到错误，发送报警
                self.send_notification_auto(
                    train_id, timestamp_text, "Route Check", "", "", "", self.current_station, f"Route {result}"
                )
                self.route_alarm_sent[train_type] = True  # 标记已发送报警

                # 显示明显的窗口通知
                self.show_route_fail_warning(train_type, timestamp_text)
        elif result == "Pass":
            # 当结果为Pass时，清除该列车的报警状态，以便下次再出错时能再次报警
            if train_type in self.route_alarm_sent:
                self.route_alarm_sent[train_type] = False

    def show_route_fail_warning(self, train_type, timestamp):
        """显示进路检查失败的明显窗口警告"""
        try:
            # 播放警告音
            winsound.Beep(2000, 500)

            # 创建警告消息框
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("⚠️ 进路检查失败 / Route Check Failure")
            msg_box.setText(f"<h3>进路排列错误检测</h3>")
            msg_box.setInformativeText(
                f"<b>列车:</b> {train_type}<br>"
                f"<b>车站:</b> SHS (Sheung Shui)<br>"
                f"<b>时间:</b> {timestamp}<br>"
                f"<b>状态:</b> <span style='color:red;font-weight:bold;'>FAIL - 进路错误</span><br><br>"
                f"<i>Wrong Route Detected! Please check immediately.</i>"
            )
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setDefaultButton(QMessageBox.Ok)

            # 设置窗口始终在最前面
            msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowStaysOnTopHint)

            # 将对话框保存为实例变量，防止被垃圾回收
            # 使用非模态方式显示，不阻塞检测线程
            self.route_fail_msg_box = msg_box
            self.route_fail_msg_box.show()
            self.route_fail_msg_box.raise_()
            self.route_fail_msg_box.activateWindow()

        except Exception as e:
            print(f"❌ 显示进路失败窗口时出错: {e}")

    # ========== 车站配置==========
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

    def load_station_config(self, station):
        """加载指定车站的配置"""
        try:
            config = self.config_loader.load_config(station)
            self.signal_id_position_setting = config["signal_id_position_setting"]
            self.regions = config["regions"]
            self.dwell_time_regions = config["dwell_time_regions"]
            self.station_region = config["station_region"]
            # 加载进路检查区域配置（如果存在）
            self.route_check_regions = config.get("route_check_regions", {})

            # 创建信号灯并初始化表格
            self.signal_lights = self.create_signal_lights()
            self.init_signal_table()

            print(f"成功加载 {station} 车站配置")
            return True
        except Exception as e:
            print(f"加载 {station} 车站配置失败: {e}")
            QMessageBox.warning(None, "配置错误", f"无法加载 {station} 车站配置: {str(e)}")
            return False

    def set_station(self, station):
        """根据选择的站点更新参数"""
        if self.load_station_config(station):
            self.current_station = station
            print(f"站点已切换至 {station}")

    # 设置函数
    def set_train_ids(self):
        input_ids = self.ui.lineEdit_3.text().strip()
        if input_ids:
            self.train_ids_setting = input_ids
            self.keywords = set(self.train_ids_setting.split(','))
            QMessageBox.information(None, "Setting Updated", "Train IDs updated successfully.")

    def set_signal_id_position(self):
        input_setting = self.ui.lineEdit_5.text().strip()
        if input_setting:
            self.signal_id_position_setting = input_setting
            config_to_save = {
                "signal_id_position_setting": input_setting,
                "regions": self.regions,  # Preserve other settings
                "dwell_time_regions": self.dwell_time_regions,
                "station_region": self.station_region
            }
            # 如果有进路检查区域配置，也保存它
            if hasattr(self, 'route_check_regions'):
                config_to_save["route_check_regions"] = self.route_check_regions
            self.config_loader.save_config_to_file(self.current_station, config_to_save)
            self.signal_lights = self.create_signal_lights()
            self.init_signal_table()
            QMessageBox.information(None, "Setting Updated", "Signal ID and Position updated successfully.")

    def set_wechat_webhook_url(self):
        webhook_url = self.ui.lineEdit_6.text().strip()
        if webhook_url:
            self.settings["WeChat Webhook URL"] = webhook_url
            QMessageBox.information(None, "Setting Updated", "WeChat Webhook URL updated successfully.")
        else:
            return

    def set_receiver_email(self):
        input_email = self.ui.lineEdit_7.text().strip()
        if input_email:
            self.settings["Receiver Email"] = input_email
            QMessageBox.information(None, "Setting Updated", "Receiver Email updated successfully.")
        else:
            return

    def set_abnormal_dwell_time(self):
        input_time_str = self.ui.lineEdit_12.text().strip()
        try:
            input_time = int(input_time_str)
            if input_time > 0:
                self.abnormal_dwell_time_setting = input_time
                QMessageBox.information(None, "Setting Updated", "Abnormal Dwell Time updated successfully.")
            else:
                QMessageBox.warning(None, "Invalid Input", "Please enter a positive integer for Abnormal Dwell Time.")
        except ValueError:
            QMessageBox.warning(None, "Invalid Input", "Please enter a valid integer for Abnormal Dwell Time.")

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
            QMessageBox.information(None, "Setting Updated", "SMTP settings updated successfully.")

        except ValueError:
            QMessageBox.warning(None, "Invalid Input", "Please enter a valid port number.")

    def create_signal_lights(self):
        signals = []
        signal_settings = self.signal_id_position_setting.split(';')
        for setting in signal_settings:
            parts = setting.split(',')
            if len(parts) >= 5:
                try:
                    signal_id = parts[0]
                    coords_str = ",".join(parts[1:5])
                    coords_tuple = eval(f"({coords_str})")
                    if isinstance(coords_tuple, tuple) and len(coords_tuple) == 4:
                        signals.append(SignalLight(signal_id, coords_tuple))
                except (ValueError, TypeError, NameError):
                    print(f"Warning: Invalid signal setting format: {setting}")
                    continue
        if not signals:
            signals = [
                SignalLight(2453, (92, 996, 106, 1008)),
                SignalLight(2536, (547, 814, 560, 826)),
                SignalLight(2502, (547, 903, 560, 918)),
                SignalLight(2501, (897, 814, 910, 827)),
                SignalLight(2533, (898, 906, 912, 916)),
                SignalLight(801, (387, 724, 402, 735)),
                SignalLight(804, (573, 724, 588, 735)),
                SignalLight(802, (572, 634, 587, 645)),
                SignalLight(809, (811, 633, 839, 645)),
                SignalLight(818, (824, 632, 840, 647)),
                SignalLight(811, (810, 723, 824, 736)),
                SignalLight(820, (827, 724, 839, 735)),
                SignalLight(825, (1063, 633, 1076, 645)),
                SignalLight(827, (1064, 723, 1077, 735)),
                SignalLight(832, (1250, 687, 1265, 700)),
                SignalLight(2753, (1258, 723, 1273, 736)),
                SignalLight(2542, (1448, 724, 1459, 739)),
                SignalLight(2540, (1445, 837, 1456, 849)),
                SignalLight(2510, (1449, 927, 1463, 940)),
                SignalLight(2509, (1678, 724, 1691, 734)),
                SignalLight(2505, (1675, 837, 1689, 848)),
                SignalLight(2546, (1764, 723, 1775, 735)),
                SignalLight(2514, (1764, 837, 1775, 848)),
                SignalLight("SB", (1869, 725, 1881, 735)),
                SignalLight("SA", (1867, 835, 1882, 849)),
                SignalLight("ceshi", (827, 421, 914, 498)),
            ]
        return signals

    def init_signal_table(self):
        self.signal_table.setRowCount(len(self.signal_lights))
        # for row, signal in enumerate(self.self.signal_lights):
        #     self.signal_table.setItem(row, 0, QTableWidgetItem(""))
        #     self.signal_table.setItem(row, 1, QTableWidgetItem(str(signal.id)))
        #     self.signal_table.setItem(row, 2, QTableWidgetItem("Detecting..."))
        for row, signal in enumerate(self.signal_lights):
            self.signal_table.setItem(row, 0, QTableWidgetItem(""))  # 列车 ID 列初始为空
            self.signal_table.setItem(row, 1, QTableWidgetItem(str(signal.id)))  # 信号灯 ID
            # 根据 signal.color 初始化颜色显示
            color_text = signal.color.upper() if signal.color != "unknown" else "Detecting..."
            item = QTableWidgetItem(color_text)
            if signal.color == "red":
                item.setForeground(QtGui.QBrush(QtGui.QColor("red")))
            elif signal.color == "blue":
                item.setForeground(QtGui.QBrush(QtGui.QColor("blue")))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor("gray")))
            self.signal_table.setItem(row, 2, item)  # 设置颜色 Item

    def startVideoStream(self):
        if self.video_started:
            return
        try:
            camera_index_str = self.ui.comboBox_32.currentText()
            camera_index = int(camera_index_str)
        except ValueError:
            QMessageBox.warning(None, "Warning", "Invalid camera index!")
            return

        # 检查摄像头是否已经打开且可用，且索引没有变化
        need_reopen = True
        if self.cap is not None and self.cap.isOpened():
            # 如果摄像头已打开，检查索引是否相同
            if self.current_camera_index == camera_index:
                # 尝试读取一帧测试摄像头是否仍然可用
                ret, test_frame = self.cap.read()
                if ret and test_frame is not None:
                    # 摄像头可用，不需要重新打开
                    need_reopen = False
                else:
                    # 摄像头已打开但无法读取，需要重新打开
                    self.cap.release()
                    self.cap = None
            else:
                # 摄像头索引变化，需要释放旧摄像头并打开新的
                self.cap.release()
                self.cap = None

        # 只有在需要时才打开摄像头
        if need_reopen:
            # 尝试打开摄像头，设置超时
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

            # 设置摄像头参数
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            # 记录当前使用的摄像头索引
            self.current_camera_index = camera_index
        self.video_started = True
        self.frame_count = 0
        self.ui.pushButton_39.setEnabled(False)
        self.ui.pushButton_42.setEnabled(True)
        self.is_running = True
        self.performance_monitor.start_run()
        # ====== 初始化两个 CSV 文件 ======
        self.init_csv()
        self.init_route_csv()

        self.timer = QTimer()
        self.timer.timeout.connect(self.captureFrame)
        self.timer.start(30)  # 主定时器：30ms (约33fps) - 保持视频流畅

        if self.signal_timer.isActive():
            self.signal_timer.stop()
        self.signal_timer.start(30)  # GPU优化：信号灯更新30ms (与主定时器同步，更快响应)

        # 定时保存 CSV
        self.periodic_csv_timer = QTimer()
        self.periodic_csv_timer.timeout.connect(self.save_csv_periodically)
        self.periodic_csv_timer.start(30000)

    def stop_detection(self):
        self.is_running = False
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        if hasattr(self, 'signal_timer') and self.signal_timer.isActive():
            self.signal_timer.stop()
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
        self.ui.pushButton_39.setEnabled(True)
        self.ui.pushButton_42.setEnabled(False)
        self.videoLabel.setText("检测已暂停")
        self.videoLabel.setStyleSheet("font-size: 16px; color: #666; background: #f0f0f0;")
        self.videoLabel.setAlignment(Qt.AlignCenter)

    def update_signal_colors(self):
        # 不再二次 cap.read()；直接复用 captureFrame() 缓存的最近一帧
        if not self.video_started or self.last_frame is None:
            return

        frame = self.last_frame  # 复用上一处缓存的帧

        for signal in self.signal_lights:
            roi = frame[signal.y1:signal.y2, signal.x1:signal.x2]
            new_color = self.get_signal_color(roi)
            if signal.color != new_color:
                signal.color = new_color

        # 你的表格刷新函数保持不变
        self.update_signal_table()

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
        self.last_frame = cv_img  # 复用给 update_signal_colors() 和其他需要的地方
        self.frame_count += 1
        self.frame_height, self.frame_width = cv_img.shape[:2]
        if self.frame_width == 0 or self.frame_height == 0:
            print("Error: Video frame has invalid dimensions")
            return

        # 非跳帧：只更新左侧视频，不做OCR
        if self.frame_count % self.frame_skip != 0:
            self.updateFrame(cv_img)
            return

        # 跳帧点：做一次信号颜色刷新 + 一次 OCR（同步）
        perf_total_start = self.performance_monitor.start_timer() if self.performance_monitor else None
        perf_ocr_start = None
        ocr_ms = None
        success_flag = True
        try:
            processed_for_signals = self.process_frame(cv_img.copy())
            self.updateFrame(processed_for_signals)  # 左侧显示框

            # OCR 只在跳帧点做一次（同步）
            if self.performance_monitor:
                perf_ocr_start = self.performance_monitor.start_timer()
            processed_for_ocr = self.performOCRAndColorDetection(cv_img)
            if self.performance_monitor and perf_ocr_start is not None:
                ocr_ms = self.performance_monitor.stop_timer(perf_ocr_start)
            qimg2 = self.convertCvToPixmap(processed_for_ocr)
            self.ocrLabel.setPixmap(qimg2.scaled(self.ocrLabel.size(), Qt.KeepAspectRatio))
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

        if self.associated_train and self.associated_signal:
            self.update_train_position()
            self.check_spad_condition()

    def updateFrame(self, cv_img):
        qimg = self.convertCvToPixmap(cv_img)
        self.videoLabel.setPixmap(qimg.scaled(self.videoLabel.size(), Qt.KeepAspectRatio))

    # def updateFrame(self, cv_img):
    #     h, w = cv_img.shape[:2]
    #     qimg = self.convertCvToPixmap(cv_img)
    #     self.videoLabel.setPixmap(qimg.scaled(self.videoLabel.size(), Qt.KeepAspectRatio))
    #     if self.video_started:
    #         processed = self.performOCRAndColorDetection(cv_img)
    #         qimg2 = self.convertCvToPixmap(processed)
    #         self.ocrLabel.setPixmap(qimg2.scaled(self.ocrLabel.size(), Qt.KeepAspectRatio))

    def process_frame(self, cv_img):
        for signal in self.signal_lights:
            roi = cv_img[signal.y1:signal.y2, signal.x1:signal.x2]
            signal.color = self.get_signal_color(roi)
            cv2.rectangle(cv_img, (signal.x1, signal.y1), (signal.x2, signal.y2), (0, 0, 255), 2)
        self.update_signal_table()
        # processed_frame = self.performOCRAndColorDetection(cv_img)
        # return processed_frame
        return cv_img

    def get_signal_color(self, roi):
        if roi.size == 0:
            return "unknown"
        roi_blur = cv2.GaussianBlur(roi, (3, 3), 0)
        hsv = cv2.cvtColor(roi_blur, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        lower_green_std = np.array([35, 50, 50])
        upper_green_std = np.array([85, 255, 255])
        lower_cyan_green = np.array([80, 50, 50])
        upper_cyan_green = np.array([100, 255, 255])
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        mask_green_std = cv2.inRange(hsv, lower_green_std, upper_green_std)
        mask_green_cyan = cv2.inRange(hsv, lower_cyan_green, upper_cyan_green)
        mask_green = cv2.bitwise_or(mask_green_std, mask_green_cyan)
        red_pixels = cv2.countNonZero(mask_red)
        green_pixels = cv2.countNonZero(mask_green)
        total_pixels = roi.shape[0] * roi.shape[1]
        red_ratio = red_pixels / total_pixels
        blue_ratio = green_pixels / total_pixels
        avg_v = np.mean(hsv[:, :, 2])
        dynamic_threshold = 0.15 if avg_v > 120 else 0.1
        if red_ratio > dynamic_threshold:
            return "red"
        elif blue_ratio > dynamic_threshold:
            return "blue"
        else:
            return "unknown"

    def update_signal_table(self):
        train_ids = sorted(list(self.detected_train_ids))
        # for row in range(len(self.signal_config)):
        #     if row < len(train_ids):
        #         self.signal_table.setItem(row, 0, QTableWidgetItem(train_ids[row]))
        #     else:
        #         self.signal_table.setItem(row, 0, QTableWidgetItem(""))
        # for row, signal in enumerate(self.signal_lights):
        #     c = signal.color.upper()
        #     item = QTableWidgetItem(c)
        #     if c == "RED":
        #         item.setForeground(QtGui.QBrush(QtGui.QColor("red")))
        #     elif c == "BLUE":
        #         item.setForeground(QtGui.QBrush(QtGui.QColor("blue")))
        #     self.signal_table.setItem(row, 2, item)
        for row in range(len(self.signal_lights)):  # 原来是 self.signal_config
            if row < len(train_ids):
                self.signal_table.setItem(row, 0, QTableWidgetItem(train_ids[row]))
            else:
                # 如果当前行超出了检测到的列车ID数量，清空第一列
                existing_item = self.signal_table.item(row, 0)
                if existing_item is None:
                    self.signal_table.setItem(row, 0, QTableWidgetItem(""))
                elif existing_item.text() != "":
                    existing_item.setText("")

            # 更新颜色列（这段逻辑现在由 update_signal_table_colors 处理更优，但保持原样以符合文件）
        for row, signal in enumerate(self.signal_lights):
            # 确保行存在
            if row < self.signal_table.rowCount():
                c = signal.color.upper()
                item = self.signal_table.item(row, 2)  # 获取现有 item
                new_text = c if c != "UNKNOWN" else "Detecting..."
                if item is None:
                    item = QTableWidgetItem(new_text)
                    self.signal_table.setItem(row, 2, item)
                elif item.text() != new_text:
                    item.setText(new_text)

                # 更新颜色
                if c == "RED":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("red")))
                elif c == "BLUE":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("blue")))
                else:  # Unknown or Detecting
                    item.setForeground(QtGui.QBrush(QtGui.QColor("gray")))

    def detect_border_color(self, original_img, abs_min_x, abs_min_y, abs_max_x, abs_max_y):
        border_width = 5
        height, width = original_img.shape[:2]
        regions = [
            (max(0, abs_min_y - border_width), abs_min_y, max(0, abs_min_x), min(width, abs_max_x)),
            (abs_max_y, min(height, abs_max_y + border_width), max(0, abs_min_x), min(width, abs_max_x)),
            (max(0, abs_min_y), min(height, abs_max_y), max(0, abs_min_x - border_width), abs_min_x),
            (max(0, abs_min_y), min(height, abs_max_y), abs_max_x, min(width, abs_max_x + border_width)),
        ]
        color_scores = defaultdict(int)
        for y1, y2, x1, x2 in regions:
            if y1 >= y2 or x1 >= x2:
                continue
            region = original_img[y1:y2, x1:x2]
            if region.size == 0:
                continue
            hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
            avg_hsv = np.mean(hsv.reshape(-1, 3), axis=0)
            h, s, v = avg_hsv
            avg_bgr = np.mean(region.reshape(-1, 3), axis=0)
            blue, green, red = avg_bgr.astype(int)
            is_green = False
            is_blue = False
            if 30 <= h <= 85 and s > 40 and v > 50:
                color_scores['green'] += 1
                is_green = True
            if not is_green:
                green_condition = (
                        blue > 160 and (blue - red) > -15 and (blue - green) > -25 and
                        (blue > green * 0.88 or blue > red * 0.9)
                )
                blue_condition = (
                        green > 155 and (green - red) > -18 and (green - blue) > 8 and abs(blue - red) < 45
                )
                if green_condition:
                    color_scores['green'] += 1
                elif blue_condition:
                    color_scores['blue'] += 1
                elif red > 180 and red > green * 1.3 and red > blue * 1.3:
                    color_scores['red'] += 1
                elif red > 200 and green > 200 and blue < 150:
                    color_scores['yellow'] += 1
                elif (abs(red - green) < 30 and abs(green - blue) < 30):
                    if red > 180:
                        color_scores['white'] += 1
                    else:
                        color_scores['gray'] += 1
        if color_scores['green'] >= 2:
            return 'green'
        if color_scores['blue'] >= 2:
            return 'blue'
        if color_scores.get('red', 0) > 0:
            return 'red'
        if color_scores.get('yellow', 0) > 0:
            return 'yellow'
        if color_scores.get('white', 0) > 0:
            return 'white'
        if color_scores.get('gray', 0) > 0:
            return 'gray'
        return 'none'

    def detect_line_status(self, cv_img, abs_min_x, abs_min_y, abs_max_x, abs_max_y):
        line_region_height = 20
        line_y_start = abs_max_y + 5
        line_y_end = line_y_start + line_region_height
        line_y_start = min(line_y_start, cv_img.shape[0] - 1)
        line_y_end = min(line_y_end, cv_img.shape[0] - 1)
        line_region = cv_img[line_y_start:line_y_end, abs_min_x:abs_max_x]
        if line_region.size == 0:
            return "No line detected"
        hsv = cv2.cvtColor(line_region, cv2.COLOR_BGR2HSV)
        green_lower = np.array([35, 43, 46])
        green_upper = np.array([77, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        red_lower1 = np.array([0, 43, 46])
        red_upper1 = np.array([10, 255, 255])
        red_lower2 = np.array([156, 43, 46])
        red_upper2 = np.array([180, 255, 255])
        red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
        red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        green_pixels = cv2.countNonZero(green_mask)
        red_pixels = cv2.countNonZero(red_mask)
        line_color = ""
        if green_pixels > red_pixels and green_pixels > 10:
            line_color = "green"
        elif red_pixels > green_pixels and red_pixels > 10:
            line_color = "red"
        else:
            return "No valid line color detected"
        gray = cv2.cvtColor(line_region, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        total_width = sum(cv2.boundingRect(cnt)[2] for cnt in contours)
        region_width = abs_max_x - abs_min_x
        is_continuous = (total_width / region_width) > 0.8
        status_map = {
            ("green", True): "Berthed, Door closed",
            ("green", False): "Berthed, Door open",
            ("red", True): "Train is detected stop, Not berthed, Door closed",
            ("red", False): "Not berthed, Door open"
        }
        return status_map.get((line_color, is_continuous), "Status unknown")

    def performOCRAndColorDetection(self, cv_img):
        if cv_img is None or cv_img.size == 0:
            return cv_img
        detected_contents = []
        timestamp_text = None
        timestamp_x0, timestamp_y0, timestamp_x1, timestamp_y1 = 1781, 75, 1903, 107
        timestamp_region = cv_img[timestamp_y0:timestamp_y1, timestamp_x0:timestamp_x1]
        timestamp_text = self.performOCRForTimestamp(timestamp_region)

        # Use current station's regions
        # Modified to handle regions as a dictionary
        region_colors = {}
        for region_id, coords in self.regions.items():
            x0, y0, x1, y1 = coords
            region_colors[region_id] = self.get_region_color(cv_img[y0:y1, x0:x1])

        orange_region = next((r_id for r_id, color in region_colors.items() if color == 'orange'), None)

        for i, (x0, y0, x1, y1) in enumerate(self.manual_partitions):
            if self.videoLabel.width() == 0 or self.frame_width == 0:
                return cv_img
            xx0 = int(x0 * self.frame_width / self.videoLabel.width())
            yy0 = int(y0 * self.frame_height / self.videoLabel.height())
            xx1 = int(x1 * self.frame_width / self.videoLabel.width())
            yy1 = int(y1 * self.frame_height / self.videoLabel.height())
            cv2.rectangle(cv_img, (xx0, yy0), (xx1, yy1), (0, 0, 255), 2)
            roi = cv_img[yy0:yy1, xx0:xx1]
            result = self.ocr.ocr(roi, cls=True)

            for line in result:
                if line:
                    for det in line:
                        text = det[1][0]
                        if re.match(r'^[A-Z]{2}\d{4}$', text):  # 动态识别例如 JM0602、JL0088 等
                            points = np.array(det[0]).astype(np.int32)
                            min_x = max(0, np.min(points[:, 0]))
                            min_y = max(0, np.min(points[:, 1]))
                            max_x = min(roi.shape[1], np.max(points[:, 0]))
                            max_y = min(roi.shape[0], np.max(points[:, 1]))
                            abs_min_x = xx0 + min_x
                            abs_min_y = yy0 + min_y
                            abs_max_x = xx0 + max_x
                            abs_max_y = yy0 + max_y

                            left_region = cv_img[abs_min_y:abs_max_y, max(0, abs_min_x - 20):abs_min_x]
                            right_region = cv_img[abs_min_y:abs_max_y, abs_max_x:min(cv_img.shape[1], abs_max_x + 20)]
                            left_color = self.get_triangle_color(left_region)
                            right_color = self.get_triangle_color(right_region)

                            status = 'Non-Reporting'
                            direction = ''
                            if left_color in ['yellow', 'orange', 'green']:
                                if left_color == 'yellow':
                                    status = 'AM'
                                elif left_color == 'orange':
                                    status = 'CM'
                                elif left_color == 'green':
                                    status = 'RM'
                                direction = 'direction A'
                            elif right_color in ['yellow', 'orange', 'green']:
                                if right_color == 'yellow':
                                    status = 'AM'
                                elif right_color == 'orange':
                                    status = 'CM'
                                elif right_color == 'green':
                                    status = 'RM'
                                direction = 'direction B'
                            if status != 'Non-Reporting' and direction:
                                status += f" {direction}"

                            # 车次中心点
                            keyword_center = ((abs_min_x + abs_max_x) // 2,
                                              (abs_min_y + abs_max_y) // 2)

                            # 距离阈值（可调），例如 80–100 像素
                            DIST_THRESHOLD = 100

                            # 用于"界面显示"的 location（站台编号），和用于内部逻辑的 real_location 分开
                            real_location = None  # 用于 dwell_time_regions 取停站时间
                            display_location = ""  # 默认不显示站台号

                            # 找到满足条件的最近 region（在扩展矩形内或距离在阈值内）
                            matched_region = None
                            min_matched_distance = float("inf")

                            for region_id, (rx0, ry0, rx1, ry1) in self.regions.items():
                                # 计算 region 中心点
                                region_center_x = (rx0 + rx1) // 2
                                region_center_y = (ry0 + ry1) // 2
                                distance_to_center = np.sqrt((keyword_center[0] - region_center_x) ** 2 +
                                                             (keyword_center[1] - region_center_y) ** 2)

                                # 检查车次中心是否在 region 矩形范围内（允许一定扩展）
                                expanded_rx0 = rx0 - DIST_THRESHOLD
                                expanded_ry0 = ry0 - DIST_THRESHOLD
                                expanded_rx1 = rx1 + DIST_THRESHOLD
                                expanded_ry1 = ry1 + DIST_THRESHOLD

                                is_in_expanded_rect = (expanded_rx0 <= keyword_center[0] <= expanded_rx1 and
                                                       expanded_ry0 <= keyword_center[1] <= expanded_ry1)

                                # 如果车次中心在扩展矩形内，或者距离在阈值内，则认为列车在此站台上
                                if is_in_expanded_rect or distance_to_center <= DIST_THRESHOLD:
                                    # 如果有多个匹配，选择最近的（距离最小的）
                                    if matched_region is None or distance_to_center < min_matched_distance:
                                        matched_region = region_id
                                        min_matched_distance = distance_to_center

                            # 如果找到了匹配的 region，设置 location
                            if matched_region is not None:
                                display_location = str(matched_region)
                                real_location = matched_region

                            border_color = self.detect_border_color(cv_img, abs_min_x, abs_min_y, abs_max_x, abs_max_y)
                            if border_color == 'green':
                                delay_text = "First train: delay <= 3:00 minute and early <= 1:00 minute"
                            elif border_color == 'yellow':
                                delay_text = "First train: delay > 3:00 minute and <= 10:00 minute"
                            elif border_color == 'red':
                                delay_text = "First train: delay > 10:00 minute"
                            elif border_color == 'blue':
                                delay_text = "First train: early > 1:00 minute"
                            elif border_color == 'black':
                                delay_text = "No time table information No information about deviation"
                            elif border_color == 'white':
                                delay_text = "No train"
                            elif border_color == 'none':
                                delay_text = "No train (layer inactive)"
                            else:
                                delay_text = ""

                            dwell_time_text = ""
                            if real_location is not None:
                                if real_location in self.dwell_time_regions:
                                    y0, y1, x0, x1 = self.dwell_time_regions[real_location]
                                    dwell_time_region = cv_img[y0:y1, x0:x1]
                                    dwell_time_result = self.ocr.ocr(dwell_time_region, cls=True)
                                    if dwell_time_result and dwell_time_result[0]:
                                        dwell_time_text = self.validate_and_correct_dwell_time(
                                            dwell_time_result[0][0][1][0])
                                else:
                                    for key_tuple, coords in self.dwell_time_regions.items():
                                        if isinstance(key_tuple, tuple) and real_location in key_tuple:
                                            y0, y1, x0, x1 = coords
                                            dwell_time_region = cv_img[y0:y1, x0:x1]
                                            dwell_time_result = self.ocr.ocr(dwell_time_region, cls=True)
                                            if dwell_time_result and dwell_time_result[0]:
                                                dwell_time_text = self.validate_and_correct_dwell_time(
                                                    dwell_time_result[0][0][1][0])
                                            break

                            station_text = self.station_name_mapping.get(self.current_station, "Unknown Station")
                            line_status = self.detect_line_status(cv_img, abs_min_x, abs_min_y, abs_max_x, abs_max_y)

                            detected_contents.append(
                                (text, status, display_location, dwell_time_text, station_text, delay_text, line_status)
                            )
                            cv2.rectangle(cv_img, (abs_min_x, abs_min_y), (abs_max_x, abs_max_y), (0, 255, 0), 2)
                            center_x = (abs_min_x + abs_max_x) // 2
                            center_y = (abs_min_y + abs_max_y) // 2
                            self.train_positions[text] = (center_x, center_y)

                            # === 新增：Route Recall Detection ===
                            # 检查第二个字母是L或M（第一个字母可能变动）
                            if len(text) >= 2 and text[1] in ["L", "M"] and self.current_station == "SHS":
                                self.route_recall_detection(cv_img, text)

        current_ids = [content[0] for content in detected_contents]
        self.detected_train_ids.update(current_ids)
        self.displayMatchingContents(detected_contents, timestamp_text)
        return cv_img

    def validate_and_correct_dwell_time(self, raw_text):
        cleaned = raw_text.strip().replace(" ", "")
        corrections = {'7': ':', 'l': '1', 'o': '0', 's': '5', 'z': '2', ' ': ''}
        for wrong, right in corrections.items():
            cleaned = cleaned.replace(wrong, right)
        if len(cleaned) > 0 and cleaned[0] not in ['+', '-']:
            cleaned = '+' + cleaned
        if len(cleaned) == 5 and cleaned[3] != ':':
            cleaned = cleaned[:3] + ':' + cleaned[4]
        elif len(cleaned) == 4:
            cleaned = cleaned[:3] + ':' + cleaned[3]
        elif len(cleaned) == 6 and cleaned[4] == ':':
            cleaned = cleaned[:3] + cleaned[4:]
        import re
        dwell_time_pattern = re.compile(r'^[+-]\d{2}:\d{2}$')
        return cleaned if dwell_time_pattern.match(cleaned) else "+00:00"

    def parse_dwell_time(self, dwell_time_str):
        try:
            if not dwell_time_str or dwell_time_str.strip() == "":
                return 0
            dwell_time_str = self.validate_and_correct_dwell_time(dwell_time_str)
            sign = -1 if dwell_time_str[0] == '-' else 1
            time_part = dwell_time_str[1:]
            if ':' in time_part:
                minutes, seconds = map(int, time_part.split(':'))
            else:
                minutes = int(time_part[:-2]) if len(time_part) > 2 else 0
                seconds = int(time_part[-2:])
            return sign * (minutes * 60 + seconds)
        except Exception as e:
            print(f"Error parsing dwell time '{dwell_time_str}': {e}")
            return 0

    def get_region_color(self, region):
        if region.size == 0:
            return 'other'
        avg_color = np.mean(region.reshape(-1, 3), axis=0)
        avg_b, avg_g, avg_r = avg_color
        if avg_r > avg_g and avg_g > avg_b and avg_r > 100:
            return 'orange'
        return 'other'

    def get_triangle_color(self, region):
        if region.size == 0:
            return 'unknown'
        avg_color = np.mean(region.reshape(-1, 3), axis=0)
        avg_b, avg_g, avg_r = avg_color
        if (abs(avg_r - avg_g) < 30 and abs(avg_g - avg_b) < 30) and (avg_r + avg_g + avg_b) / 3 < 150:
            return 'gray'
        elif avg_r > 100 and avg_g > 180 and avg_b < 220:
            return 'yellow'
        elif avg_r > 200 and avg_g > 100 and avg_b < 100 and avg_g > avg_b:
            return 'orange'
        elif avg_g > avg_r and avg_g > avg_b and avg_g > 150:
            return 'green'
        return 'unknown'

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

    def displayMatchingContents(self, detected_contents, timestamp_text):
        if not timestamp_text:
            timestamp_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # self.init_csv()
        for content in detected_contents:
            text, status, location, dwell_time_text, station_text, delay_text, line_status = content
            rowpos = self.trainTable.rowCount()
            self.trainTable.insertRow(rowpos)
            self.trainTable.setItem(rowpos, 0, QTableWidgetItem(text))
            self.trainTable.setItem(rowpos, 1, QTableWidgetItem(timestamp_text))
            self.trainTable.setItem(rowpos, 2, QTableWidgetItem(status))
            self.trainTable.setItem(rowpos, 3, QTableWidgetItem(delay_text))
            self.trainTable.setItem(rowpos, 4, QTableWidgetItem(dwell_time_text))
            # 如果location为None或空字符串,则Location列留空,不显示站台编号
            if location is None or str(location).strip() == "":
                self.trainTable.setItem(rowpos, 5, QTableWidgetItem(""))
            else:
                self.trainTable.setItem(rowpos, 5, QTableWidgetItem(str(location)))
            self.trainTable.setItem(rowpos, 6, QTableWidgetItem(station_text))
            self.trainTable.setItem(rowpos, 7, QTableWidgetItem(line_status))
            self.save_to_csv(text, timestamp_text, status, delay_text, dwell_time_text, location, station_text,
                             line_status)
            dwell_seconds = self.parse_dwell_time(dwell_time_text)
            if dwell_seconds is not None and dwell_seconds > self.abnormal_dwell_time_setting:
                print(
                    f"🚨 Train {text} dwell time exceeded {self.abnormal_dwell_time_setting} seconds! ({dwell_seconds}s)")
                try:
                    winsound.Beep(1500, 800)
                except Exception as e:
                    print(f"Sound alert error: {e}")
                self.send_notification_auto(text, timestamp_text, status, delay_text, dwell_time_text, location,
                                            station_text, line_status)
            if self.auto_scroll_enabled:
                self.trainTable.scrollToBottom()

    # def send_notification_auto(self, train_id, timestamp, status, delay, dwell_time, location, station, door_status):
    #     msg = (
    #         f"⚠️ Dwell Time Alert ⚠️\n\n"
    #         f"Train ID: {train_id}\n"
    #         f"Date/Time: {timestamp}\n"
    #         f"Status: {status}\n"
    #         f"Delay: {delay}\n"
    #         f"Dwell Time: {dwell_time}\n"
    #         f"Location: {location}\n"
    #         f"Station: {station}\n"
    #         f"Door: {door_status}"
    #     )
    #     payload = {"msgtype": "text", "text": {"content": msg}}
    #     try:
    #         resp = requests.post(self.settings.get("WeChat Webhook URL"), json=payload)
    #         if resp.status_code == 200:
    #             print("✅ WeChat notification sent automatically.")
    #         else:
    #             print(f"❌ Failed to send WeChat notification. Code: {resp.status_code}")
    #     except Exception as e:
    #         print(f"❌ Error sending WeChat notification: {e}")

    def send_notification_auto(self, train_id, timestamp, status, delay, dwell_time, location, station, door_status):
        """
        自动发送企业微信通知。
        当 status == "Route Check" 且结果 Fail 时，发送：
          (2025-09-15 13:00:00 Wrong Route Detected for Train JL0327)
        其它情况保持原有逻辑。
        """
        try:
            # ===== 新增分支：进路检查 =====
            # if str(status).strip().lower() == "route check":
            #     result_str = (door_status or "").strip().lower()
            #     is_fail = ("fail" in result_str) or ("wrong" in result_str)
            if str(status).strip().lower() == "route check":
                result_str = (door_status or "").strip().lower()

                # 1️⃣ Fail 报警
                is_fail = ("fail" in result_str) or ("wrong" in result_str)
                if is_fail:
                    msg = f"({timestamp} Wrong Route Detected for Train {train_id})"
                    webhook_url = self.settings.get("WeChat Webhook URL")
                    if webhook_url:
                        try:
                            requests.post(webhook_url, json={"msgtype": "text", "text": {"content": msg}})
                            print(f"✅ WeChat sent: {msg}")
                        except Exception as e:
                            print(f"❌ WeChat send error: {e}")
                    return

                # 2️⃣ Clear 通知（错误被纠正）
                if "clear" in result_str:
                    msg = f"({timestamp} Wrong Route Detected for Train {train_id} Clear)"
                    webhook_url = self.settings.get("WeChat Webhook URL")
                    if webhook_url:
                        try:
                            requests.post(webhook_url, json={"msgtype": "text", "text": {"content": msg}})
                            print(f"✅ WeChat sent correction: {msg}")
                        except Exception as e:
                            print(f"❌ WeChat send error: {e}")
                    return

                if is_fail:
                    msg = f"({timestamp} Wrong Route Detected for Train {train_id})"
                    webhook_url = self.settings.get("WeChat Webhook URL")
                    if webhook_url:
                        try:
                            requests.post(webhook_url, json={"msgtype": "text", "text": {"content": msg}})
                            print(f"✅ WeChat sent: {msg}")
                        except Exception as e:
                            print(f"❌ WeChat send error: {e}")
                    else:
                        print("WeChat Webhook URL not configured. Skipping route notification.")
                return  # Route Check 分支结束

            # ===== 原有分支逻辑：保持不变 =====
            msg = (
                f"Train Alert\n"
                f"Time: {timestamp}\n"
                f"Train ID: {train_id}\n"
                f"Status: {status}\n"
                f"Delay: {delay}\n"
                f"Dwell Time: {dwell_time}\n"
                f"Location: {location}\n"
                f"Station: {station}\n"
                f"Door: {door_status}"
            )

            webhook_url = self.settings.get("WeChat Webhook URL")
            if webhook_url:
                try:
                    requests.post(webhook_url, json={"msgtype": "text", "text": {"content": msg}})
                    print("✅ WeChat notification sent automatically.")
                except Exception as e:
                    print(f"❌ Error sending WeChat notification: {e}")
            else:
                print("WeChat Webhook URL not configured. Skipping notification.")

        except Exception as e:
            print(f"❌ send_notification_auto error: {e}")

    # ========== OCR CSV 存储 ==========
    def init_csv(self):
        output_folder = "output_data"
        os.makedirs(output_folder, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        csv_file_path = os.path.join(output_folder, f"train_ocr_results_{timestamp}.csv")
        if not self.csv_writer:
            self.csv_file = open(csv_file_path, "a", newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            if self.csv_file.tell() == 0:
                self.csv_writer.writerow(
                    ["Train ID", "Date/Time", "Status", "Delay", "Dwell", "Location", "Station", "Door"]
                )
            print(f"📄 Train OCR CSV created: {csv_file_path}")

    # def save_to_csv(self, train_id, date_time, status, delay_text, dwell_time_text, location, station_text, line_status):
    #     if self.csv_writer:
    #         try:
    #             self.csv_writer.writerow([train_id, date_time, status, delay_text,
    #                                       dwell_time_text, location, station_text, line_status])
    #         except Exception as e:
    #             print(f"Write OCR CSV exception: {e}")

    # ========== Route CSV 存储 ==========
    def init_route_csv(self):
        output_folder = "output_data"
        os.makedirs(output_folder, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        route_file_path = os.path.join(output_folder, f"route_check_log_{timestamp}.csv")
        if not getattr(self, "route_csv_writer", None):  # 确保属性存在
            self.route_csv_file = open(route_file_path, "a", newline="", encoding="utf-8")
            self.route_csv_writer = csv.writer(self.route_csv_file)
            if self.route_csv_file.tell() == 0:
                self.route_csv_writer.writerow(
                    ["Timestamp", "Train ID Type", "SHS Route",
                     "LMC Route", "LOW Route", "Route Check", "Alert"]  # 多一列
                )
            print(f"📄 Route check CSV created: {route_file_path}")

    def save_route_check_to_csv(self, timestamp, train_type,
                                shs_result, lmc_result, low_result,
                                check_result, alert=""):
        if getattr(self, "route_csv_writer", None):
            try:
                self.route_csv_writer.writerow([
                    timestamp, train_type, shs_result,
                    lmc_result, low_result, check_result, alert
                ])
                                
                # 【新增】同步推送到AI Assistant
                if push_route_check_data:
                    try:
                        push_route_check_data(timestamp, train_type, shs_result, lmc_result, low_result, check_result, alert)
                    except:
                        pass
                        
            except Exception as e:
                print(f"❌ Write Route CSV exception: {e}")

    # ========== 停止/定时保存 ==========
    def save_csv_on_stop(self):
        if self.csv_file:
            try:
                self.csv_file.flush()
                print("OCR CSV 数据已在停止时保存。")
            except Exception as e:
                print(f"停止时保存 OCR CSV 出错: {e}")
        if self.route_csv_file:
            try:
                self.route_csv_file.flush()
                print("Route CSV 数据已在停止时保存。")
            except Exception as e:
                print(f"停止时保存 Route CSV 出错: {e}")

    def save_csv_periodically(self):
        if self.csv_file:
            try:
                self.csv_file.flush()
                print("OCR CSV 数据已定期保存。")
            except Exception as e:
                print(f"定期保存 OCR CSV 出错: {e}")
        if self.route_csv_file:
            try:
                self.route_csv_file.flush()
                print("Route CSV 数据已定期保存。")
            except Exception as e:
                print(f"定期保存 Route CSV 出错: {e}")

    # 这个函数会不断向csv文件中更新，随时打开随时更新
    def save_to_csv(self, train_id, date_time, status, delay_text, dwell_time_text, location, station_text,
                    line_status):
        if self.csv_file:
            self.csv_writer.writerow(
                [train_id, date_time, status, delay_text, dwell_time_text, location, station_text, line_status])
            self.csv_file.flush()
                        
            # 【新增】同步推送到AI Assistant
            if push_train_data:
                try:
                    push_train_data(train_id, date_time, status, delay_text, dwell_time_text, location, station_text, line_status)
                except:
                    pass

    def associate_items(self):
        sel = self.signal_table.selectedIndexes()
        cols = [i.column() for i in sel]
        if cols.count(0) != 1 or cols.count(1) != 1:
            QMessageBox.warning(None, "Selection Error", "Please select one train (col0) and one signal (col1).")
            return
        train_row = next(i.row() for i in sel if i.column() == 0)
        signal_row = next(i.row() for i in sel if i.column() == 1)
        train_id_item = self.signal_table.item(train_row, 0)
        signal_id_item = self.signal_table.item(signal_row, 1)
        if not train_id_item or not signal_id_item:
            QMessageBox.warning(None, "Error", "Train or Signal invalid.")
            return
        train_id = train_id_item.text()
        sid = signal_id_item.text()
        sig = next((s for s in self.signal_lights if str(s.id) == sid), None)
        if not sig:
            QMessageBox.warning(None, "Error", "Signal not found.")
            return
        if train_id not in self.train_positions:
            QMessageBox.warning(None, "Error", "Train position not found.")
            return
        t_x, t_y = self.train_positions[train_id]
        self.spadMonitor.setItem(1, 0, QTableWidgetItem(
            f"Train Coordinates: ({t_x},{t_y}), Signal Coordinates: ({sig.center[0]},{sig.center[1]})"))
        self.associated_train = train_id
        self.associated_signal = sig
        self.spadMonitor.setItem(0, 0, QTableWidgetItem(f"Associated: {train_id} with Signal {sid}"))

    def cancel_association(self):
        self.associated_train = None
        self.associated_signal = None
        self.train_crossing_status.clear()
        self.spadMonitor.setItem(0, 0, QTableWidgetItem("Association canceled"))
        self.spadMonitor.setItem(1, 0, QTableWidgetItem("Waiting..."))

    def update_train_position(self):
        if self.associated_train in self.train_positions and self.associated_signal:
            x, y = self.train_positions[self.associated_train]
            sig_x = self.associated_signal.center[0]
            self.spadMonitor.setItem(1, 0, QTableWidgetItem(f"Train X: {x}, Signal X: {sig_x}"))
            new_status = "left"
            if x > sig_x + 10:
                new_status = "right"
            elif abs(x - sig_x) <= 10:
                new_status = "at_signal"
            old_status = self.train_crossing_status.get(self.associated_train, None)
            if new_status != old_status:
                self.train_crossing_status[self.associated_train] = new_status
                self.check_status_change()

    def check_status_change(self):
        cur = self.train_crossing_status.get(self.associated_train)
        if cur in ["left", "right"] and self.associated_signal and self.associated_signal.color == "red":
            self.check_spad_condition()

    def check_spad_condition(self):
        if not self.associated_signal or self.spad_detected:
            return
        if self.associated_signal.color != "red":
            return
        cur = self.train_crossing_status.get(self.associated_train)
        if cur not in ["left", "right"]:
            return
        prev = self.previous_train_status.get(self.associated_train)
        if prev and prev != cur:
            self.trigger_spad_alert()
        self.previous_train_status[self.associated_train] = cur

    def trigger_spad_alert(self):
        self.spad_detected = True
        winsound.Beep(2000, 1000)
        item = QTableWidgetItem("SPAD Occurred!")
        item.setForeground(QColor("red"))
        item.setFont(QFont("Arial", weight=QFont.Bold))
        self.spadMonitor.setItem(0, 0, item)

    def start_spad_detection(self):
        if self.associated_train and self.associated_signal:
            self.spad_detected = False
            self.previous_train_status = {}
            self.train_crossing_status = {}
            self.spad_timer = QTimer()
            self.spad_timer.timeout.connect(self.check_spad_condition)
            self.spad_timer.start(1000)
            item = QTableWidgetItem("SPAD Detection Active")
            item.setForeground(QColor("green"))
            self.spadMonitor.setItem(0, 0, item)

    def resetDetectionRegion(self):
        self.manual_partitions.clear()
        self.videoLabel.update()

    def cancelLastSelection(self):
        if self.manual_partitions:
            self.manual_partitions.pop()
        self.videoLabel.update()

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
                # 调整坐标顺序，确保x0 <= x1，y0 <= y1
                x0 = min(self.start_x, self.end_x)
                x1 = max(self.start_x, self.end_x)
                y0 = min(self.start_y, self.end_y)
                y1 = max(self.start_y, self.end_y)
                # 确保区域至少1像素宽高
                if x1 - x0 > 1 and y1 - y0 > 1:
                    self.manual_partitions.append((x0, y0, x1, y1))
                self.videoLabel.update()
                return True

            # 绘制选择框
            elif event.type() == QEvent.Paint and self.is_selecting:
                painter = QPainter(self.videoLabel)
                painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
                # 计算矩形区域
                rx = min(self.start_x, self.end_x)
                ry = min(self.start_y, self.end_y)
                rw = abs(self.end_x - self.start_x)
                rh = abs(self.end_y - self.start_y)
                # 绘制半透明选择框
                painter.setBrush(QColor(255, 0, 0, 50))  # 红色半透明填充
                painter.drawRect(rx, ry, rw, rh)
                return False

        return super().eventFilter(obj, event)

    def play_sound_alert(self):
        row = self.trainTable.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to play the sound alert.")
            return
        try:
            winsound.Beep(1000, 500)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to play sound: {e}")

    def send_notification(self):
        row = self.trainTable.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to send a WeChat notification.")
            return
        ocr_data = [self.trainTable.item(row, col).text() if self.trainTable.item(row, col) else "" for col in
                    range(self.trainTable.columnCount())]
        msg = (
            f"Train ID: {ocr_data[0]}\n"
            f"Date/Time: {ocr_data[1]}\n"
            f"Status: {ocr_data[2]}\n"
            f"Delay: {ocr_data[3]}\n"
            f"Dwell Time: {ocr_data[4]}\n"
            f"Location: {ocr_data[5]}\n"
            f"Station: {ocr_data[6]}\n"
            f"Door: {ocr_data[7]}\n"
        )
        payload = {"msgtype": "text", "text": {"content": msg}}
        try:
            resp = requests.post(self.settings.get("WeChat Webhook URL"), json=payload)
            if resp.status_code == 200:
                QMessageBox.information(None, "Notification Sent", "WeChat notification sent.")
            else:
                QMessageBox.warning(None, "Error", f"Failed. Code: {resp.status_code}")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Send notification error: {e}")

    def send_email(self):
        row = self.trainTable.currentRow()
        if row == -1:
            QMessageBox.warning(None, "No Selection", "Please select a row to send email.")
            return
        data = [self.trainTable.item(row, col).text() if self.trainTable.item(row, col) else "" for col in
                range(self.trainTable.columnCount())]
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        subject = f"OCR Notification - {timestamp}"
        body = (
            f"Train ID: {data[0]}\n"
            f"Date/Time: {data[1]}\n"
            f"Status: {data[2]}\n"
            f"Delay: {data[3]}\n"
            f"Dwell Time: {data[4]}\n"
            f"Location: {data[5]}\n"
            f"Station: {data[6]}\n"
            f"Door: {data[7]}\n"
        )
        message = MIMEMultipart()
        message["From"] = self.settings.get("Sender email")
        message["To"] = self.settings.get("Receiver Email")
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))
        try:
            server = smtplib.SMTP_SSL(self.settings.get("Smtp server"), self.settings.get("Smtp port"))
            server.login(self.settings.get("Sender email"), self.settings.get("Sender password"))
            server.send_message(message)
            server.quit()
            QMessageBox.information(None, "Email Sent", "Email was sent successfully.")
        except smtplib.SMTPAuthenticationError:
            QMessageBox.warning(None, "Error", "Auth failed. Check email or auth code.")
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to send email: {e}")

    def close_all(self):
        try:
            self.stop_detection()
        except Exception as e:
            print(f"关闭列车检测时出现异常: {e}")

        if self.cap:
            self.cap.release()
            self.cap = None
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
        if hasattr(self, 'signal_timer') and self.signal_timer.isActive():
            self.signal_timer.stop()

    def convertCvToPixmap(self, cv_img):
        h, w, ch = cv_img.shape
        bytes_per_line = ch * w
        return QtGui.QPixmap.fromImage(QtGui.QImage(cv_img.data, w, h, bytes_per_line, QtGui.QImage.Format_BGR888))