"""
GPU运行环境：
- GPU: NVIDIA GeForce RTX 4090 (24GB)
- CUDA: 12.8 / 11.8
- Python: 3.11.3
- PaddlePaddle-GPU: 3.0.0-beta2
- PaddleOCR: 3.1.0
"""

import sys
import cv2
import csv
import difflib
import smtplib
import winsound
import time
import requests
import threading

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QTimer, QDateTime, Qt, QEvent
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen
from PyQt5.QtWidgets import (
    QTableWidgetItem, QMessageBox, QVBoxLayout, QAbstractItemView
)
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ======= 引入UI文件 =======
from PageTurning2 import Ui_Dialog as MainWindowUI
from Register import Ui_Dialog as RegisterUI

# 后端功能模块
from alarmlist import AlarmListIntegration
from power import PowerIntegration
from turnout import TurnoutIntegration
from train import TrainIntegration
import resource_rc  # 若有资源文件


class RegisterDialog(QtWidgets.QDialog):
    """注册对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = RegisterUI()
        self.ui.setupUi(self)
        self.setup_connections()

    def setup_connections(self):
        self.ui.pushButton_3.clicked.connect(self.handle_register)
        self.ui.commandLinkButton_2.clicked.connect(self.back_to_login)

    def handle_register(self):
        username = self.ui.lineEdit_3.text().strip()
        pwd1 = self.ui.lineEdit_4.text().strip()
        pwd2 = self.ui.lineEdit_5.text().strip()
        if pwd1 == pwd2:
            if username == "" or pwd1 == "":
                QtWidgets.QMessageBox.warning(self, "Error", "Username or password cannot be empty!")
                return
            try:
                with open('user.csv', 'a', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([username, pwd1])
                QtWidgets.QMessageBox.information(self, "Success",
                                                  "Registration successful, returning to the login screen soon.")
                self.accept()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Failed to write user data: {e}")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "The password entered twice is inconsistent!")

    def back_to_login(self):
        self.accept()


class LoginWindow(QtWidgets.QDialog):
    """登录对话框"""
    def __init__(self):
        super().__init__()
        self.ui = MainWindowUI()
        self.ui.setupUi(self)
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_13)
        self.setup_connections()
        self.setFixedSize(1920, 1030)

    def setup_connections(self):
        self.ui.pushButton.clicked.connect(self.handle_login)
        self.ui.commandLinkButton.clicked.connect(self.show_register)

    def handle_login(self):
        username = self.ui.lineEdit.text().strip()
        password = self.ui.lineEdit_2.text().strip()
        if not username or not password:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter your username and password!")
            return

        try:
            found = False
            with open('user.csv', 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if len(row) >= 2 and row[0] == username and row[1] == password:
                        found = True
                        break
            if found:
                self.accept()
            else:
                QtWidgets.QMessageBox.warning(self, "Warning", "Username or password is incorrect!")
        except FileNotFoundError:
            QtWidgets.QMessageBox.warning(self, "Warning", "No user data found. Please register first.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"An error occurred: {e}")

    def show_register(self):
        register_dialog = RegisterDialog(self)
        if register_dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.show()


class MainWindow(QtWidgets.QMainWindow):
    """主窗口，承载PageTurning UI + 三大后端功能"""
    def __init__(self):
        super().__init__()
        self.ui = MainWindowUI()
        self.ui.setupUi(self)
        self.is_logged_in = True
        self.setup_navigation()
        self.fix_table_headers1()
        self.fix_table_headers2()

        self.ui.stackedWidget.setCurrentWidget(self.ui.page_2)
        self.setFixedSize(1920, 1030)

        self.connect_login_page()

        # 初始化后端功能
        self.alarm_integration = AlarmListIntegration(self.ui)
        self.ui.pushButton_57.clicked.connect(self.toggle_auto_scroll_57)
        self.ui.pushButton_57.setToolTip("点击暂停自动滚动")

        self.power_integration = PowerIntegration(self.ui)
        self.ui.pushButton_60.clicked.connect(self.toggle_auto_scroll_60)
        self.ui.pushButton_60.setToolTip("点击暂停自动滚动")

        self.turnout_integration = TurnoutIntegration(self.ui)
        self.ui.pushButton_58.clicked.connect(self.toggle_auto_scroll_58)
        self.ui.pushButton_58.setToolTip("点击暂停自动滚动")

        self.train_integration = TrainIntegration(self.ui)
        self.ui.pushButton_59.clicked.connect(self.toggle_auto_scroll_59)
        self.ui.pushButton_59.setToolTip("点击暂停自动滚动")

        self.ui.frame_20.installEventFilter(self)
        self.is_selecting = False
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None

        # Group 1: Point and Point Analysis (道岔与道岔分析)
        self.point_sync_combos = [self.ui.comboBox_28, self.ui.comboBox_25]
        for combo in self.point_sync_combos:
            combo.currentIndexChanged.connect(self.sync_point_combos)

        # Group 2: Train and SPAD Detection (列车与SPAD检测)
        self.train_sync_combos = [self.ui.comboBox_27, self.ui.comboBox_10]
        for combo in self.train_sync_combos:
            combo.currentIndexChanged.connect(self.sync_train_combos)

        # Independent ComboBoxes (独立下拉框)
        # Connect each to its respective backend logic without syncing others
        self.ui.comboBox_26.currentTextChanged.connect(self.power_integration.set_station)  # For Power
        # comboBox_12 (Login) does not require a backend connection

    def connect_login_page(self):
        self.ui.pushButton.clicked.connect(self.handle_login_from_main)
        self.ui.commandLinkButton.clicked.connect(self.show_register_from_main)

    # --- NEW: Synchronization function for Point group ---
    def sync_point_combos(self):
        """同步道岔(Point)相关的下拉框 (28, 25)"""
        sender_combo = self.sender()
        if sender_combo:
            station = sender_combo.currentText()

            # Update TurnoutIntegration backend
            self.turnout_integration.on_station_changed(station)

            # Sync the other combo in the point group
            for combo in self.point_sync_combos:
                if combo is not sender_combo:
                    combo.blockSignals(True)
                    combo.setCurrentText(station)
                    combo.blockSignals(False)

    # --- NEW: Synchronization function for Train group ---
    def sync_train_combos(self):
        """同步列车(Train)相关的下拉框 (27, 10)"""
        sender_combo = self.sender()
        if sender_combo:
            station = sender_combo.currentText()

            # Update TrainIntegration backend
            self.train_integration.set_station(station)

            # Sync the other combo in the train group
            for combo in self.train_sync_combos:
                if combo is not sender_combo:
                    combo.blockSignals(True)
                    combo.setCurrentText(station)
                    combo.blockSignals(False)

    def closeEvent(self, event):
        self.alarm_integration.close_all()
        self.power_integration.close_all()
        self.turnout_integration.close_all()
        self.train_integration.close_all()
        QtWidgets.qApp.quit()

    def setup_navigation(self):
        nav_mapping = {
            self.ui.pushButton_9: self.ui.page_2,
            self.ui.pushButton_7: self.ui.page_5,
            self.ui.pushButton_8: self.ui.page_6,
            self.ui.pushButton_10: self.ui.page_7,
            self.ui.pushButton_11: self.ui.page_8,
            self.ui.pushButton_12: self.ui.page_10,
            self.ui.pushButton_14: self.ui.page_12,
        }
        for btn, target in nav_mapping.items():
            btn.clicked.connect(lambda _, p=target: self.switch_page(p))
        self.ui.pushButton_15.clicked.connect(self.logout)

    def fix_table_headers1(self):
        corner_style = """
            QTableWidget QTableCornerButton::section {
                background-color: #2f5597 !important;
                border: 1px solid #2f5597;
            }
        """
        tables = [
            self.ui.tableWidget_2,
            self.ui.tableWidget_3,
            self.ui.tableWidget_4,
            self.ui.tableWidget_5,
            self.ui.tableWidget_6,
        ]
        for table in tables:
            table.horizontalHeader().setVisible(True)
            table.verticalHeader().setVisible(True)
            table.setCornerButtonEnabled(True)
            original_style = table.styleSheet()
            if "QTableCornerButton::section" not in original_style:
                new_style = f"{original_style}\n{corner_style}"
                table.setStyleSheet(new_style.strip())
            table.style().unpolish(table)
            table.style().polish(table)
            table.update()

    def fix_table_headers2(self):
        corner_style = """
            QTableWidget QTableCornerButton::section {
                background-color: #2f5597 !important;
                border: 1px solid #2f5597;
            }
        """
        tables = [self.ui.tableWidget_7]
        for table in tables:
            table.horizontalHeader().setVisible(False)
            table.verticalHeader().setVisible(True)
            original_style = table.styleSheet()
            if "QTableCornerButton::section" not in original_style:
                new_style = f"{original_style}\n{corner_style}"
                table.setStyleSheet(new_style.strip())
            table.style().unpolish(table)
            table.style().polish(table)
            table.update()

    def switch_page(self, page):
        if self.is_logged_in:
            self.ui.stackedWidget.setCurrentWidget(page)
        else:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please log in to the system first！")

    def logout(self):
        self.is_logged_in = False
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_13)
        self.ui.lineEdit.clear()
        self.ui.lineEdit_2.clear()

    def handle_login_from_main(self):
        username = self.ui.lineEdit.text().strip()
        password = self.ui.lineEdit_2.text().strip()
        if not username or not password:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please enter your username and password！")
            return

        try:
            found = False
            with open('user.csv', 'r', newline='') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if len(row) >= 2 and row[0] == username and row[1] == password:
                        found = True
                        break
            if found:
                self.is_logged_in = True
                self.ui.stackedWidget.setCurrentWidget(self.ui.page_2)
            else:
                QtWidgets.QMessageBox.warning(self, "Warning", "Username or password is incorrect!")
        except FileNotFoundError:
            QtWidgets.QMessageBox.warning(self, "Warning", "No user data found. Please register first.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"An error occurred: {e}")

    def show_register_from_main(self):
        register_dialog = RegisterDialog(self)
        if register_dialog.exec_() == QtWidgets.QDialog.Accepted:
            pass

    def toggle_auto_scroll_57(self):
        self.alarm_integration.auto_scroll_enabled = not self.alarm_integration.auto_scroll_enabled
        self.ui.pushButton_57.setToolTip("自动滚动已开启，点击暂停" if self.alarm_integration.auto_scroll_enabled else "自动滚动已暂停，点击恢复")

    def toggle_auto_scroll_58(self):
        self.turnout_integration.auto_scroll_enabled = not self.turnout_integration.auto_scroll_enabled
        self.ui.pushButton_58.setToolTip("自动滚动已开启，点击暂停" if self.turnout_integration.auto_scroll_enabled else "自动滚动已暂停，点击恢复")

    def toggle_auto_scroll_59(self):
        self.train_integration.auto_scroll_enabled = not self.train_integration.auto_scroll_enabled
        self.ui.pushButton_59.setToolTip("自动滚动已开启，点击暂停" if self.train_integration.auto_scroll_enabled else "自动滚动已暂停，点击恢复")

    def toggle_auto_scroll_60(self):
        self.power_integration.auto_scroll_enabled = not self.power_integration.auto_scroll_enabled
        self.ui.pushButton_60.setToolTip("自动滚动已开启，点击暂停" if self.power_integration.auto_scroll_enabled else "自动滚动已暂停，点击恢复")

    def eventFilter(self, obj, event):
        if obj is self.ui.frame_20:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if self.ui.stackedWidget.currentWidget() == self.ui.page_5:
                    self.is_selecting = True
                    self.start_x = event.pos().x()
                    self.start_y = event.pos().y()
                    self.end_x = self.start_x
                    self.end_y = self.start_y
                    return True
            elif event.type() == QEvent.MouseMove:
                if self.is_selecting:
                    self.end_x = event.pos().x()
                    self.end_y = event.pos().y()
                    self.ui.frame_20.update()
                    return True
            elif event.type() == QEvent.MouseButtonRelease and self.is_selecting and event.button() == Qt.LeftButton:
                self.is_selecting = False
                if self.ui.stackedWidget.currentWidget() == self.ui.page_5:
                    rect_start_x, rect_start_y, rect_end_x, rect_end_y = self.start_x, self.start_y, self.end_x, self.end_y
                    self.turnout_integration.manual_partitions.append((rect_start_x, rect_start_y, rect_end_x, rect_end_y))
                    return True
            elif event.type() == QEvent.Paint and self.is_selecting and self.ui.stackedWidget.currentWidget() == self.ui.page_5:
                painter = QPainter(self.ui.frame_20)
                painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
                rect = QtCore.QRect(QtCore.QPoint(self.start_x, self.start_y), QtCore.QPoint(self.end_x, self.end_y))
                painter.drawRect(rect.normalized())
                return False
        return super().eventFilter(obj, event)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    font = QtGui.QFont("Times New Roman", 10)
    app.setFont(font)

    login = LoginWindow()
    if login.exec_() == QtWidgets.QDialog.Accepted:
        main_window = MainWindow()
        main_window.show()
        sys.exit(app.exec_())
    else:
        sys.exit()