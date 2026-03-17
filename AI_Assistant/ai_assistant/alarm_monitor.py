"""
实时报警监控
监控 output_data 文件夹中的新报警信息
"""

import os
import csv
import time
import logging
import threading
from pathlib import Path
from typing import List, Dict, Callable, Optional
from datetime import datetime
from collections import deque
import pandas as pd

from config import OUTPUT_DATA_DIR, ALARM_MONITOR_INTERVAL, MAX_RECENT_ALARMS
from csv_parser import CSVParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlarmMonitor:
    """报警监控器"""
    
    def __init__(self, output_data_dir: Path = OUTPUT_DATA_DIR):
        """
        初始化报警监控器
        
        Args:
            output_data_dir: 输出数据目录
        """
        self.output_data_dir = Path(output_data_dir)
        self.recent_alarms = deque(maxlen=MAX_RECENT_ALARMS)
        self.file_timestamps = {}  # 记录文件的最后修改时间
        self.callbacks = []  # 回调函数列表
        self.is_running = False
        self.monitor_thread = None
        
        logger.info(f"✓ 报警监控器初始化完成，监控目录: {self.output_data_dir}")
    
    def register_callback(self, callback: Callable[[Dict], None]):
        """
        注册回调函数，当检测到新报警时调用
        
        Args:
            callback: 回调函数，接收报警数据字典作为参数
        """
        self.callbacks.append(callback)
        logger.info(f"✓ 注册回调函数: {callback.__name__}")
    
    def start(self):
        """启动监控"""
        if self.is_running:
            logger.warning("监控器已在运行")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("✓ 报警监控已启动")
    
    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("✓ 报警监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        logger.info("开始监控报警文件...")
        
        while self.is_running:
            try:
                self._check_for_new_alarms()
                time.sleep(ALARM_MONITOR_INTERVAL)
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(ALARM_MONITOR_INTERVAL)
    
    def _check_for_new_alarms(self):
        """检查新报警"""
        if not self.output_data_dir.exists():
            logger.warning(f"输出目录不存在: {self.output_data_dir}")
            return
        
        # 遍历所有 CSV 文件
        for csv_file in self.output_data_dir.glob("*.csv"):
            try:
                # 获取文件修改时间
                current_mtime = csv_file.stat().st_mtime
                last_mtime = self.file_timestamps.get(str(csv_file), 0)
                
                # 如果文件被修改或是新文件
                if current_mtime > last_mtime:
                    self._process_alarm_file(csv_file, last_mtime > 0)
                    self.file_timestamps[str(csv_file)] = current_mtime
                    
            except Exception as e:
                logger.error(f"处理文件失败 {csv_file}: {e}")
    
    def _process_alarm_file(self, csv_file: Path, is_update: bool = False):
        """
        处理报警文件（使用统一解析器）
        
        Args:
            csv_file: CSV 文件路径
            is_update: 是否是文件更新（而非新文件）
        """
        try:
            # 使用统一的 CSV 解析器
            alarm_data_list = CSVParser.parse_csv(str(csv_file))
            
            if not alarm_data_list:
                return
            
            # 如果是更新，只处理最新的几条记录
            if is_update:
                recent_alarms = alarm_data_list[-5:]  # 最新5条
            else:
                recent_alarms = alarm_data_list[-10:]  # 最新10条
            
            # 处理每条报警记录
            for alarm_data in recent_alarms:
                # 检查是否已处理过（避免重复）
                if not self._is_duplicate(alarm_data):
                    self._on_new_alarm(alarm_data)
                    
        except Exception as e:
            logger.debug(f"处理文件时出错 {csv_file.name}: {str(e)}")
    
    def _parse_alarm_record(self, row: pd.Series, source_file: Path) -> Dict:
        """
        解析报警记录
        
        Args:
            row: DataFrame 行
            source_file: 源文件路径
            
        Returns:
            报警数据字典
        """
        alarm_data = {
            'timestamp': datetime.now().isoformat(),
            'source_file': source_file.name,
            'source_path': str(source_file)
        }
        
        # 添加所有列的数据
        for col in row.index:
            value = row[col]
            if pd.notna(value):
                alarm_data[col] = value
        
        # 尝试提取标准字段
        self._extract_standard_fields(alarm_data, row)
        
        return alarm_data
    
    def _extract_standard_fields(self, alarm_data: Dict, row: pd.Series):
        """提取标准字段"""
        # 尝试识别时间戳字段
        for time_col in ['timestamp', 'time', 'date', 'datetime', '时间']:
            if time_col in row.index and pd.notna(row[time_col]):
                alarm_data['detected_time'] = str(row[time_col])
                break
        
        # 尝试识别站点字段
        for station_col in ['station', 'Station', '站点', '车站']:
            if station_col in row.index and pd.notna(row[station_col]):
                alarm_data['station'] = str(row[station_col])
                break
        
        # 尝试识别报警类型字段
        for type_col in ['alarm_type', 'type', 'alert_type', '报警类型', '类型']:
            if type_col in row.index and pd.notna(row[type_col]):
                alarm_data['alarm_type'] = str(row[type_col])
                break
        
        # 尝试识别描述字段
        for desc_col in ['description', 'desc', 'message', '描述', '信息']:
            if desc_col in row.index and pd.notna(row[desc_col]):
                alarm_data['description'] = str(row[desc_col])
                break
        
        # 尝试识别严重程度
        for sev_col in ['severity', 'level', 'priority', '严重程度', '等级']:
            if sev_col in row.index and pd.notna(row[sev_col]):
                alarm_data['severity'] = str(row[sev_col])
                break
    
    def _is_duplicate(self, alarm_data: Dict) -> bool:
        """检查是否是重复报警"""
        # 简单的重复检查：比较最近的报警
        for recent_alarm in list(self.recent_alarms)[-10:]:
            # 比较关键字段
            if (alarm_data.get('station') == recent_alarm.get('station') and
                alarm_data.get('alarm_type') == recent_alarm.get('alarm_type') and
                alarm_data.get('description') == recent_alarm.get('description')):
                return True
        return False
    
    def _on_new_alarm(self, alarm_data: Dict):
        """处理新报警"""
        # 添加到最近报警列表
        self.recent_alarms.append(alarm_data)
        
        logger.info(f"检测到新报警: {alarm_data.get('alarm_type', 'Unknown')} - {alarm_data.get('station', 'N/A')}")
        
        # 调用所有回调函数
        for callback in self.callbacks:
            try:
                callback(alarm_data)
            except Exception as e:
                logger.error(f"回调函数执行失败 {callback.__name__}: {e}")
    
    def get_recent_alarms(self, count: int = 20) -> List[Dict]:
        """
        获取最近的报警
        
        Args:
            count: 返回数量
            
        Returns:
            最近的报警列表
        """
        return list(self.recent_alarms)[-count:]
    
    def get_alarm_summary(self) -> Dict:
        """获取报警摘要统计"""
        if not self.recent_alarms:
            return {
                'total': 0,
                'by_type': {},
                'by_station': {},
                'by_severity': {}
            }
        
        alarms_list = list(self.recent_alarms)
        df = pd.DataFrame(alarms_list)
        
        summary = {
            'total': len(alarms_list),
            'by_type': {},
            'by_station': {},
            'by_severity': {}
        }
        
        # 按类型统计
        if 'alarm_type' in df.columns:
            summary['by_type'] = df['alarm_type'].value_counts().to_dict()
        
        # 按站点统计
        if 'station' in df.columns:
            summary['by_station'] = df['station'].value_counts().to_dict()
        
        # 按严重程度统计
        if 'severity' in df.columns:
            summary['by_severity'] = df['severity'].value_counts().to_dict()
        
        return summary
    
    def clear_recent_alarms(self):
        """清空最近报警列表"""
        self.recent_alarms.clear()
        logger.info("✓ 已清空最近报警列表")


# 测试回调函数
def test_callback(alarm_data: Dict):
    """测试回调函数"""
    print(f"\n[新报警] {datetime.now().strftime('%H:%M:%S')}")
    print(f"  类型: {alarm_data.get('alarm_type', 'N/A')}")
    print(f"  站点: {alarm_data.get('station', 'N/A')}")
    print(f"  描述: {alarm_data.get('description', 'N/A')}")


# 测试函数
def test_alarm_monitor():
    """测试报警监控器"""
    print("=" * 60)
    print("测试报警监控器")
    print("=" * 60)
    
    # 创建监控器
    monitor = AlarmMonitor()
    
    # 注册回调
    monitor.register_callback(test_callback)
    
    # 启动监控
    monitor.start()
    
    print(f"\n✓ 监控已启动，监控目录: {OUTPUT_DATA_DIR}")
    print("  监控中... (Ctrl+C 停止)")
    
    try:
        while True:
            time.sleep(10)
            # 显示摘要
            summary = monitor.get_alarm_summary()
            print(f"\n[摘要] 共 {summary['total']} 条报警")
    except KeyboardInterrupt:
        print("\n正在停止监控...")
        monitor.stop()
        print("✓ 监控已停止")


if __name__ == "__main__":
    test_alarm_monitor()

