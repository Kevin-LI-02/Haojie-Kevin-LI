"""
精确查询模块
用于处理需要精确结果的查询（时间敏感、统计类）
直接读取CSV文件进行结构化查询，避免向量检索的不确定性
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)


class PreciseQuery:
    """精确查询处理器"""
    
    def __init__(self, dal_logs_dir: str):
        """
        初始化精确查询处理器
        
        Args:
            dal_logs_dir: DAL日志目录路径
        """
        self.dal_logs_dir = Path(dal_logs_dir)
        self.df_cache = None  # 缓存加载的数据
    
    def _load_dal_logs(self) -> pd.DataFrame:
        """
        加载所有DAL日志文件
        
        Returns:
            合并后的DataFrame
        """
        if self.df_cache is not None:
            return self.df_cache
        
        all_dfs = []
        
        # 查找所有CSV文件
        csv_files = list(self.dal_logs_dir.glob("*.csv"))
        
        if not csv_files:
            logger.warning(f"未找到DAL日志文件: {self.dal_logs_dir}")
            return pd.DataFrame()
        
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                
                # 确保有必要的列
                if 'timestamp' in df.columns and 'station' in df.columns:
                    # 转换时间戳
                    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                    all_dfs.append(df)
                    logger.debug(f"✓ 加载 DAL 日志: {csv_file.name}, {len(df)} 条记录")
                else:
                    logger.warning(f"⚠️ 文件缺少必要列: {csv_file.name}")
                    
            except Exception as e:
                logger.error(f"❌ 读取文件失败 {csv_file.name}: {e}")
        
        if not all_dfs:
            logger.warning("未成功加载任何DAL日志")
            return pd.DataFrame()
        
        # 合并所有DataFrame
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        # 按时间戳排序
        combined_df = combined_df.sort_values('timestamp', ascending=False)
        
        # 缓存
        self.df_cache = combined_df
        
        logger.info(f"✓ 共加载 {len(combined_df)} 条DAL日志记录")
        
        return combined_df
    
    def query_latest_alarms(
        self, 
        station: Optional[str] = None, 
        alarm_type: Optional[str] = None,
        limit: int = 10,
        order: str = 'latest'  # 'latest'=最新（降序）, 'earliest'=最早（升序）
    ) -> List[Dict]:
        """
        查询最新或最早的报警记录
        
        Args:
            station: 车站代码（如LMC、SHS）
            alarm_type: 报警类型（如列车超速、道岔故障）
            limit: 返回记录数量
            order: 'latest'（最新，降序）或 'earliest'（最早，升序）
            
        Returns:
            报警记录列表
        """
        df = self._load_dal_logs()
        
        if df.empty:
            return []
        
        # 过滤条件
        filtered_df = df.copy()
        
        if station:
            station_upper = station.upper()
            filtered_df = filtered_df[
                filtered_df['station'].str.upper() == station_upper
            ]
            logger.info(f"  过滤条件: 车站={station_upper}")
        
        if alarm_type:
            filtered_df = filtered_df[
                filtered_df['alarm_type'].str.contains(alarm_type, na=False)
            ]
            logger.info(f"  过滤条件: 报警类型={alarm_type}")
        
        # 根据 order 参数决定排序方向
        if order == 'earliest':
            # 最早：升序排序
            filtered_df = filtered_df.sort_values('timestamp', ascending=True)
            logger.info(f"  排序: 按时间升序（最早在前）")
            order_label = "最早"
        else:
            # 最新：降序排序（已经在 _load_dal_logs 中完成）
            logger.info(f"  排序: 按时间降序（最新在前）")
            order_label = "最新"
        
        # 取前N条
        result_df = filtered_df.head(limit)
        
        # 转换为字典列表
        results = []
        for _, row in result_df.iterrows():
            results.append({
                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['timestamp']) else 'N/A',
                'station': row.get('station', 'N/A'),
                'alarm_type': row.get('alarm_type', 'N/A'),
                'description': row.get('description', 'N/A'),
                'severity': row.get('severity', 'N/A')
            })
        
        logger.info(f"✓ 精确查询返回 {len(results)} 条{order_label}记录")
        
        return results
    
    def query_alarm_count(
        self,
        station: Optional[str] = None,
        alarm_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Dict:
        """
        统计报警次数
        
        Args:
            station: 车站代码
            alarm_type: 报警类型
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            year: 年份
            month: 月份
            
        Returns:
            统计结果字典
        """
        df = self._load_dal_logs()
        
        if df.empty:
            return {'count': 0, 'records': []}
        
        # 过滤条件
        filtered_df = df.copy()
        
        if station:
            station_upper = station.upper()
            filtered_df = filtered_df[
                filtered_df['station'].str.upper() == station_upper
            ]
            logger.info(f"  统计条件: 车站={station_upper}")
        
        if alarm_type:
            filtered_df = filtered_df[
                filtered_df['alarm_type'].str.contains(alarm_type, na=False)
            ]
            logger.info(f"  统计条件: 报警类型={alarm_type}")
        
        # 时间范围过滤
        if year and month:
            filtered_df = filtered_df[
                (filtered_df['timestamp'].dt.year == year) &
                (filtered_df['timestamp'].dt.month == month)
            ]
            logger.info(f"  统计条件: 时间={year}年{month}月")
        elif year:
            filtered_df = filtered_df[
                filtered_df['timestamp'].dt.year == year
            ]
            logger.info(f"  统计条件: 时间={year}年")
        elif start_date and end_date:
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            filtered_df = filtered_df[
                (filtered_df['timestamp'] >= start) &
                (filtered_df['timestamp'] <= end)
            ]
            logger.info(f"  统计条件: 时间={start_date}至{end_date}")
        
        count = len(filtered_df)
        
        # 提取记录详情（最多20条）
        records = []
        for _, row in filtered_df.head(20).iterrows():
            records.append({
                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['timestamp']) else 'N/A',
                'station': row.get('station', 'N/A'),
                'alarm_type': row.get('alarm_type', 'N/A'),
                'description': row.get('description', 'N/A'),
                'severity': row.get('severity', 'N/A')
            })
        
        logger.info(f"✓ 精确统计: 共 {count} 条记录")
        
        return {
            'count': count,
            'records': records,
            'has_more': count > 20
        }
    
    @staticmethod
    def should_use_precise_query(question: str, classification: Dict) -> bool:
        """
        判断是否应该使用精确查询
        
        Args:
            question: 用户问题
            classification: 问题分类结果
            
        Returns:
            True 如果应该使用精确查询
        """
        question_type = classification.get('type')
        
        # 1. 历史统计类问题 -> 需要精确统计
        if question_type in ['statistics', 'recent_event']:
            return True
        
        # 2. 包含明确的时间关键词 -> 需要精确查询
        time_keywords = [
            '最近', '最新', '上次', '最后一次', '最后', '刚刚',
            '几次', '多少次', '次数', '统计', '发生',
            'recent', 'latest', 'last', 'how many', 'count'
        ]
        
        if any(kw in question.lower() for kw in time_keywords):
            return True
        
        return False
    
    @staticmethod
    def extract_query_params(question: str, classification: Dict) -> Dict:
        """
        从问题中提取查询参数
        
        Args:
            question: 用户问题
            classification: 问题分类结果
            
        Returns:
            查询参数字典
        """
        params = {
            'station': classification.get('entities', {}).get('station'),
            'alarm_type': classification.get('alarm_type')
        }
        
        # 提取年份和月份
        year_match = re.search(r'(\d{4})年', question)
        month_match = re.search(r'(\d{1,2})月', question)
        
        if year_match:
            params['year'] = int(year_match.group(1))
        if month_match:
            params['month'] = int(month_match.group(1))
        
        # 【新增】识别"最早"vs"最新"
        question_lower = question.lower()
        if any(kw in question_lower for kw in ['最早', '第一次', '首次', 'earliest', 'first', 'initial']):
            params['order'] = 'earliest'  # 最早（升序）
        elif any(kw in question_lower for kw in ['最新', '最近', '最后', '刚刚', 'latest', 'recent', 'last']):
            params['order'] = 'latest'    # 最新（降序）
        else:
            params['order'] = 'latest'    # 默认最新
        
        # 提取时间范围关键词
        time_range = classification.get('time_range', {})
        if time_range:
            params['time_range'] = time_range
        
        return params


def test_precise_query():
    """测试精确查询功能"""
    import os
    from pathlib import Path
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # 获取DAL日志目录
    current_dir = Path(__file__).parent
    dal_logs_dir = current_dir / 'data' / 'dal_logs'
    
    if not dal_logs_dir.exists():
        print(f"❌ 目录不存在: {dal_logs_dir}")
        return
    
    pq = PreciseQuery(str(dal_logs_dir))
    
    print("=" * 80)
    print("精确查询功能测试")
    print("=" * 80)
    
    # 测试1: 查询LMC站最新报警
    print("\n【测试1】查询LMC站最新报警")
    print("-" * 80)
    results = pq.query_latest_alarms(station='LMC', limit=3)
    for i, record in enumerate(results, 1):
        print(f"{i}. {record['timestamp']} | {record['alarm_type']} | {record['description']} | {record['severity']}")
    
    # 测试2: 统计2024年11月LMC站报警次数
    print("\n【测试2】统计2024年11月LMC站报警次数")
    print("-" * 80)
    stats = pq.query_alarm_count(station='LMC', year=2024, month=11)
    print(f"总计: {stats['count']} 次")
    print("详细记录:")
    for i, record in enumerate(stats['records'], 1):
        print(f"  {i}. {record['timestamp']} | {record['alarm_type']}")
    
    # 测试3: 统计道岔故障次数
    print("\n【测试3】统计道岔故障总次数")
    print("-" * 80)
    stats = pq.query_alarm_count(alarm_type='道岔故障')
    print(f"总计: {stats['count']} 次")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_precise_query()

