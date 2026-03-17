"""
统一的 CSV 文件解析器
自动识别并解析不同模块生成的 CSV 文件
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CSVParser:
    """统一的 CSV 文件解析器"""
    
    # 定义不同模块的 CSV 格式Schema
    CSV_SCHEMAS = {
        "alarmlist": {
            "columns": ["Date/Time", "Area", "Sub Area", "Object", "Text", "Action"],
            "alt_columns": {"suggested Action": "Action"},  # 列名映射
            "required": [],  # 不强制要求，因为可能有空行
            "alarm_type": "Alarm List",
            "description": "报警列表",
            "priority_field": "Text"
        },
        "train": {
            "columns": ["Train ID", "Date/Time", "Status", "Delay", "Dwell Time", "Location", "Station", "Door"],
            "alt_columns": {"Dwell": "Dwell Time"},  # 列名映射
            "required": [],  # 不强制要求
            "alarm_type": "Train",
            "description": "列车监控",
            "priority_field": "Status"
        },
        "turnout": {
            "columns": ["Turnout ID", "Date/Time", "Status", "Throw Time", "Text"],
            "required": ["Turnout ID"],
            "alarm_type": "Turnout",
            "description": "道岔监控",
            "priority_field": "Status"
        },
        "power": {
            "columns": ["Date/Time", "ID", "Description", "Status"],
            "required": ["ID"],
            "alarm_type": "Power",
            "description": "电源系统",
            "priority_field": "Status"
        },
        "route_check": {
            "columns": ["Timestamp", "Train ID Type", "SHS Route", "LMC Route", "LOW Route", "Route Check", "Alert"],
            "required": ["Train ID Type"],
            "alarm_type": "Route Check",
            "description": "进路检查",
            "priority_field": "Route Check"
        }
    }
    
    @staticmethod
    def detect_csv_type(filepath: str) -> str:
        """
        根据文件名自动检测 CSV 类型
        
        Args:
            filepath: CSV 文件路径
            
        Returns:
            CSV 类型标识
        """
        filename = Path(filepath).name.lower()
        
        if "alarmlist" in filename:
            return "alarmlist"
        elif "train" in filename and "route" not in filename:
            return "train"
        elif "turnout" in filename:
            return "turnout"
        elif "power" in filename:
            return "power"
        elif "route" in filename:
            return "route_check"
        else:
            return "unknown"
    
    @staticmethod
    def parse_csv(filepath: str, max_rows: int = 100) -> List[Dict]:
        """
        解析 CSV 文件，自动识别类型并规范化数据
        
        Args:
            filepath: CSV 文件路径
            max_rows: 最多读取的行数（避免大文件占用过多内存）
            
        Returns:
            标准化的报警数据列表
        """
        try:
            # 检查文件是否存在和大小
            file_path = Path(filepath)
            if not file_path.exists():
                logger.debug(f"文件不存在: {filepath}")
                return []
            
            if file_path.stat().st_size == 0:
                logger.debug(f"跳过空文件: {filepath}")
                return []
            
            # 读取 CSV
            try:
                df = pd.read_csv(
                    filepath,
                    encoding='utf-8-sig',  # 处理 BOM
                    on_bad_lines='skip',    # 跳过格式错误的行
                    nrows=max_rows          # 限制读取行数
                )
            except pd.errors.EmptyDataError:
                logger.debug(f"CSV 文件为空: {filepath}")
                return []
            except Exception as e:
                logger.debug(f"读取 CSV 失败 {filepath}: {e}")
                return []
            
            if df.empty:
                return []
            
            # 检测 CSV 类型
            csv_type = CSVParser.detect_csv_type(filepath)
            
            logger.debug(f"解析 CSV: {file_path.name} (类型: {csv_type}, 行数: {len(df)})")
            
            if csv_type == "unknown":
                # 未知类型，尝试通用解析
                results = CSVParser._generic_parse(df, filepath)
            else:
                # 使用对应的 schema 解析
                results = CSVParser._schema_parse(df, csv_type, filepath)
            
            return results
            
        except Exception as e:
            logger.debug(f"解析 CSV 异常 {filepath}: {e}")
            return []
    
    @staticmethod
    def _schema_parse(df: pd.DataFrame, csv_type: str, filepath: str) -> List[Dict]:
        """
        使用预定义的 schema 解析 CSV
        
        Args:
            df: DataFrame
            csv_type: CSV 类型
            filepath: 文件路径
            
        Returns:
            标准化数据列表
        """
        schema = CSVParser.CSV_SCHEMAS.get(csv_type)
        if not schema:
            return CSVParser._generic_parse(df, filepath)
        
        # 处理列名映射（如 "suggested Action" -> "Action"）
        if "alt_columns" in schema:
            for alt_col, standard_col in schema["alt_columns"].items():
                if alt_col in df.columns and standard_col not in df.columns:
                    df = df.rename(columns={alt_col: standard_col})
                    logger.debug(f"列名映射: '{alt_col}' -> '{standard_col}'")
        
        results = []
        
        # 遍历每一行
        for idx, row in df.iterrows():
            # 跳过完全空行（所有值都是 NaN 或空字符串）
            if row.isna().all():
                continue
            
            # 检查是否是有效行（至少有一个非空的关键字段）
            has_valid_data = False
            for col in df.columns:
                value = row[col]
                if pd.notna(value) and str(value).strip():
                    has_valid_data = True
                    break
            
            if not has_valid_data:
                continue
            # 基础数据
            alarm_data = {
                "alarm_type": schema["alarm_type"],
                "description": schema["description"],
                "source_file": Path(filepath).name,
                "source_path": filepath,
                "row_index": idx
            }
            
            # 尝试获取时间戳
            timestamp = CSVParser._extract_timestamp(row)
            if timestamp:
                alarm_data["timestamp"] = timestamp
            else:
                alarm_data["timestamp"] = datetime.now().isoformat()
            
            # 添加所有列的数据
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    # 清理字符串
                    if isinstance(value, str):
                        value = value.strip()
                    alarm_data[col] = str(value)
            
            # 提取关键信息字段
            CSVParser._extract_key_info(alarm_data, schema)
            
            results.append(alarm_data)
        
        logger.info(f"✓ 成功解析 {len(results)} 条 {schema['description']} 记录")
        return results
    
    @staticmethod
    def _generic_parse(df: pd.DataFrame, filepath: str) -> List[Dict]:
        """
        通用解析（未知格式的 CSV）
        
        Args:
            df: DataFrame
            filepath: 文件路径
            
        Returns:
            标准化数据列表
        """
        results = []
        
        for idx, row in df.iterrows():
            alarm_data = {
                "alarm_type": "Unknown",
                "description": "未知类型",
                "source_file": Path(filepath).name,
                "source_path": filepath,
                "row_index": idx
            }
            
            # 尝试提取时间戳
            timestamp = CSVParser._extract_timestamp(row)
            if timestamp:
                alarm_data["timestamp"] = timestamp
            else:
                alarm_data["timestamp"] = datetime.now().isoformat()
            
            # 添加所有数据
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    if isinstance(value, str):
                        value = value.strip()
                    alarm_data[col] = str(value)
            
            # 尝试提取关键信息
            alarm_data["key_info"] = CSVParser._guess_key_info(alarm_data)
            
            results.append(alarm_data)
        
        logger.info(f"✓ 通用解析 {len(results)} 条记录 (未知格式)")
        return results
    
    @staticmethod
    def _extract_timestamp(row: pd.Series) -> Optional[str]:
        """
        从行数据中提取时间戳
        
        Args:
            row: DataFrame 行
            
        Returns:
            ISO 格式的时间戳字符串
        """
        # 可能的时间戳列名
        timestamp_columns = [
            "Date/Time", "Timestamp", "Time", "DateTime",
            "时间", "日期时间", "时间戳"
        ]
        
        for col in timestamp_columns:
            if col in row.index:
                value = row[col]
                if pd.notna(value):
                    try:
                        # 尝试解析时间
                        if isinstance(value, str):
                            # 尝试多种时间格式
                            for fmt in [
                                "%Y-%m-%d %H:%M:%S",
                                "%Y/%m/%d %H:%M:%S",
                                "%d.%m.%Y %H:%M:%S",
                                "%Y-%m-%dT%H:%M:%S"
                            ]:
                                try:
                                    dt = datetime.strptime(value, fmt)
                                    return dt.isoformat()
                                except:
                                    continue
                        # 如果是 pandas Timestamp
                        elif hasattr(value, 'isoformat'):
                            return value.isoformat()
                    except:
                        pass
        
        return None
    
    @staticmethod
    def _extract_key_info(alarm_data: Dict, schema: Dict):
        """
        提取关键信息字段
        
        Args:
            alarm_data: 报警数据字典
            schema: CSV schema
        """
        key_info_parts = []
        
        # 根据类型提取关键信息
        alarm_type = alarm_data.get("alarm_type", "")
        
        if alarm_type == "Train":
            # 列车: Train ID + Status + Station
            train_id = alarm_data.get("Train ID", "")
            status = alarm_data.get("Status", "")
            station = alarm_data.get("Station", "")
            # 过滤掉空值
            key_info_parts = [p for p in [train_id, status, station] if p and str(p).strip()]
            
        elif alarm_type == "Turnout":
            # 道岔: Turnout ID + Status
            turnout_id = alarm_data.get("Turnout ID", "")
            status = alarm_data.get("Status", "")
            key_info_parts = [p for p in [turnout_id, status] if p and str(p).strip()]
            
        elif alarm_type == "Power":
            # 电源: ID + Description + Status
            power_id = alarm_data.get("ID", "")
            desc = alarm_data.get("Description", "")
            status = alarm_data.get("Status", "")
            key_info_parts = [p for p in [power_id, desc, status] if p and str(p).strip()]
            
        elif alarm_type == "Alarm List":
            # 报警列表: Area + Sub Area + Object + Text
            area = alarm_data.get("Area", "")
            sub_area = alarm_data.get("Sub Area", "")
            obj = alarm_data.get("Object", "")
            text = alarm_data.get("Text", "")
            # 优先显示有内容的字段
            key_info_parts = [p for p in [area, sub_area, obj, text] if p and str(p).strip()]
            
        elif alarm_type == "Route Check":
            # 进路检查: Train ID + Result
            train_id = alarm_data.get("Train ID Type", "")
            result = alarm_data.get("Route Check", "")
            alert = alarm_data.get("Alert", "")
            key_info_parts = [p for p in [train_id, result, alert] if p and str(p).strip()]
        
        # 组合关键信息，限制长度避免过长
        if key_info_parts:
            key_info = " - ".join(str(p)[:50] for p in key_info_parts[:4])  # 最多4个字段，每个最多50字符
        else:
            key_info = "N/A"
        
        alarm_data["key_info"] = key_info
    
    @staticmethod
    def _guess_key_info(alarm_data: Dict) -> str:
        """
        猜测未知格式数据的关键信息
        
        Args:
            alarm_data: 报警数据字典
            
        Returns:
            关键信息字符串
        """
        # 尝试找到最有价值的字段
        priority_fields = []
        
        for key, value in alarm_data.items():
            if key in ["alarm_type", "description", "source_file", "timestamp", "row_index"]:
                continue
            
            # 关键字段优先
            if any(kw in key.lower() for kw in ["id", "status", "text", "description", "alarm"]):
                priority_fields.insert(0, str(value))
            else:
                priority_fields.append(str(value))
        
        # 最多取前3个字段
        return " - ".join(priority_fields[:3]) if priority_fields else "N/A"
    
    @staticmethod
    def get_supported_types() -> Dict[str, Dict]:
        """
        获取支持的 CSV 类型列表
        
        Returns:
            类型字典
        """
        return CSVParser.CSV_SCHEMAS.copy()


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # 测试解析
    import os
    output_dir = Path("../output_data")
    
    if output_dir.exists():
        print("=" * 60)
        print("CSV 解析器测试")
        print("=" * 60)
        
        csv_files = list(output_dir.glob("*.csv"))
        print(f"\n找到 {len(csv_files)} 个 CSV 文件\n")
        
        for csv_file in csv_files[:5]:  # 只测试前5个
            print(f"\n处理: {csv_file.name}")
            print("-" * 60)
            
            results = CSVParser.parse_csv(str(csv_file))
            
            if results:
                print(f"✓ 成功解析 {len(results)} 条记录")
                print(f"  类型: {results[0].get('alarm_type')}")
                print(f"  关键信息示例: {results[0].get('key_info')}")
            else:
                print("✗ 解析失败或无数据")
        
        print("\n" + "=" * 60)
        print("✓ 测试完成")
    else:
        print(f"输出目录不存在: {output_dir}")

