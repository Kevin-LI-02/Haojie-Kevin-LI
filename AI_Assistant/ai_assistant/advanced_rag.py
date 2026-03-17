"""
高级 RAG 系统
针对大规模 DAL Logs 和 Work Instructions 的智能检索
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


class AdvancedRAG:
    """高级 RAG 检索器"""
    
    # 铁路/轨道交通领域关键词库（用于判断问题是否与专业领域相关）
    DOMAIN_KEYWORDS = {
        # 报警类型
        'alarms': ['超速', '道岔', '转辙', '电源', '供电', '信号', '通信', '进路', '脱轨', '紧急制动',
                  'overspeed', 'turnout', 'switch', 'power', 'signal', 'derailment', 'emergency brake'],
        
        # 设备和系统
        'equipment': ['列车', '车辆', '轨道', 'ats', 'atc', 'atp', '联锁', '闭塞', '信号机', '应答器',
                     'train', 'track', 'vehicle', 'interlocking', 'balise', 'transponder'],
        
        # 车站和线路
        'stations': ['lmc', 'shs', 'low', '低窝', '上水', '罗湖', '车站', '站场', '线路', '正线', '侧线',
                    'station', 'depot', 'mainline', 'siding'],
        
        # 操作和流程
        'operations': ['调度', '行车', '运营', '值班', '司机', '调度员', '确认', '防护', '隔离', '复位',
                      'dispatch', 'operation', 'driver', 'dispatcher', 'reset', 'isolate'],
        
        # 技术术语
        'technical': ['dal', 'log', '报警', '故障', '监控', 'eyes-t', 'ocr', '识别', '处置',
                     'alarm', 'fault', 'monitoring', 'detection', 'disposal']
    }
    
    # 问题类型分类（按匹配优先级排序！）
    QUESTION_PATTERNS = {
        # 最近事件类（需要 DAL Logs）- 【优先级最高】包含最早/最新
        'recent_event': {
            'keywords': ['最近', '上次', '最后一次', '最新', '刚刚', '最早', '第一次', '首次',
                        'recent', 'last', 'latest', 'just', 'earliest', 'first', 'initial'],
            'priority': 'dal_log',
            'description': '最近事件查询（包含最早/最新）'
        },
        
        # 历史统计类（需要 DAL Logs）- 【注意：移除了"最近"避免冲突】
        'statistics': {
            'keywords': ['几次', '多少次', '频率', '统计', '发生', '次数', '过去',
                        'frequency', 'count', 'times', 'how many', 'statistics'],
            'priority': 'dal_log',
            'description': '历史统计查询'
        },
        
        # 操作流程类（需要 Work Instructions）
        'procedure': {
            'keywords': ['如何', '怎么', '怎样', '处理', '处置', '操作', '步骤', '应该', '方法', '流程', '规范',
                        'how', 'what', 'procedure', 'handle', 'process', 'should'],
            'priority': 'work_instruction',
            'description': '操作流程查询'
        },
        
        # 定义解释类（优先 Work Instructions，辅助 DAL Logs）
        'definition': {
            'keywords': ['是什么', '什么是', '定义', '含义', '介绍', '功能',
                        'what is', 'define', 'definition', 'meaning'],
            'priority': 'work_instruction',
            'description': '定义解释查询'
        }
    }
    
    # 报警类型关键词映射
    ALARM_TYPE_KEYWORDS = {
        '列车超速': ['列车超速', '超速', 'overspeed', 'train speed'],
        '道岔故障': ['道岔', '转辙', 'turnout', 'switch', 'point'],
        '电源故障': ['电源', '供电', 'power', 'electricity'],
        '信号故障': ['信号', 'signal'],
        '通信故障': ['通信', '通讯', 'communication'],
        '进路故障': ['进路', 'route'],
    }
    
    @staticmethod
    def is_domain_relevant(question: str) -> bool:
        """
        判断问题是否与铁路/轨道交通领域相关
        
        Args:
            question: 用户问题
            
        Returns:
            True 如果问题与铁路领域相关，False 否则
        """
        question_lower = question.lower()
        
        # 【优先级1】核心铁路术语（强制判定为专业）
        core_terms = ['ats', 'atc', 'atp', 'dal', 'eyes-t', 'eyes_t', 'eyest', '联锁', '闭塞']
        for term in core_terms:
            if term in question_lower:
                logger.info(f"  ✓ 领域相关性检测: 是 (识别到核心术语: '{term}')")
                return True
        
        # 【优先级2】检查是否包含实体（列车编号、站点）
        entities = AdvancedRAG._extract_entities(question)
        if entities.get('train_id') or entities.get('station'):
            logger.info(f"  ✓ 领域相关性检测: 是 (识别到实体: {entities})")
            return True
        
        # 【优先级3】统计领域关键词匹配数量
        match_count = 0
        matched_categories = []
        matched_keywords = []
        
        for category, keywords in AdvancedRAG.DOMAIN_KEYWORDS.items():
            category_matches = [kw for kw in keywords if kw in question_lower]
            if category_matches:
                match_count += len(category_matches)
                matched_categories.append(category)
                matched_keywords.extend(category_matches[:2])  # 只记录前2个，避免日志过长
        
        # 判断逻辑：
        # 1. 匹配到至少2个关键词，或
        # 2. 匹配到至少2个不同类别的关键词
        is_relevant = match_count >= 2 or len(matched_categories) >= 2
        
        if is_relevant:
            logger.info(f"  ✓ 领域相关性检测: 是 (匹配{match_count}个关键词，覆盖{len(matched_categories)}个类别: {matched_categories[:3]})")
        else:
            logger.info(f"  ✗ 领域相关性检测: 否 (仅匹配{match_count}个关键词: {matched_keywords}，不足以判定为专业问题)")
        
        return is_relevant
    
    @staticmethod
    def classify_question(question: str) -> Dict:
        """
        分类用户问题（两级分类：先判断领域相关性，再判断问题类型）
        
        Returns:
            {
                'type': 'procedure' | 'statistics' | 'recent_event' | 'definition' | 'general',
                'alarm_type': '列车超速' | '道岔故障' | None,
                'priority_source': 'work_instruction' | 'dal_log' | None,
                'is_domain_relevant': bool,  # 【新增】是否与铁路领域相关
                'is_professional': bool,     # 【新增】是否应使用专业模式
                'description': str
            }
        """
        question_lower = question.lower()
        
        # ========== 第一级：领域相关性检测 ==========
        is_domain_relevant = AdvancedRAG.is_domain_relevant(question)
        
        # ========== 第二级：问题类型分类 ==========
        # 1. 识别问题类型
        question_type = 'general'
        priority_source = None
        
        for q_type, pattern in AdvancedRAG.QUESTION_PATTERNS.items():
            if any(kw in question_lower for kw in pattern['keywords']):
                question_type = q_type
                priority_source = pattern['priority']
                break
        
        # 2. 识别报警类型
        alarm_type = None
        for alarm, keywords in AdvancedRAG.ALARM_TYPE_KEYWORDS.items():
            if any(kw in question_lower for kw in keywords):
                alarm_type = alarm
                break
        
        # 3. 提取时间范围
        time_range = AdvancedRAG._extract_time_range(question)
        
        # 4. 提取实体（列车编号、站点等）
        entities = AdvancedRAG._extract_entities(question)
        
        # ========== 最终判定：是否应使用专业模式 ==========
        # 规则：必须同时满足以下条件之一：
        # 1. 识别到明确的报警类型（如"列车超速"、"道岔故障"）-> 强制专业模式
        # 2. 问题类型为专业类型 AND 领域相关
        professional_types = ['procedure', 'statistics', 'recent_event', 'definition']
        
        if alarm_type:
            # 明确的报警类型，强制使用专业模式
            is_professional = True
            logger.info(f"  → 判定: 专业问题（识别到报警类型: {alarm_type}）")
        elif question_type in professional_types and is_domain_relevant:
            # 问题模式匹配且领域相关
            is_professional = True
            logger.info(f"  → 判定: 专业问题（{question_type} + 领域相关）")
        else:
            # 其他情况：通用问题
            is_professional = False
            if question_type in professional_types:
                logger.info(f"  → 判定: 通用问题（{question_type} 但不属于铁路领域）")
            else:
                logger.info(f"  → 判定: 通用问题（{question_type}）")
        
        return {
            'type': question_type,
            'alarm_type': alarm_type,
            'priority_source': priority_source,
            'time_range': time_range,
            'entities': entities,
            'is_domain_relevant': is_domain_relevant,
            'is_professional': is_professional,
            'description': AdvancedRAG.QUESTION_PATTERNS.get(question_type, {}).get('description', '通用查询')
        }
    
    @staticmethod
    def _extract_time_range(question: str) -> Optional[Dict]:
        """提取时间范围"""
        time_patterns = {
            r'过去(\d+)个月': lambda m: {'months': int(m.group(1))},
            r'过去(\d+)周': lambda m: {'weeks': int(m.group(1))},
            r'过去(\d+)天': lambda m: {'days': int(m.group(1))},
            r'最近(\d+)个月': lambda m: {'months': int(m.group(1))},
            r'最近(\d+)天': lambda m: {'days': int(m.group(1))},
            r'今天': lambda m: {'days': 0},
            r'昨天': lambda m: {'days': 1},
            r'本周': lambda m: {'weeks': 1},
            r'本月': lambda m: {'months': 1},
        }
        
        for pattern, extractor in time_patterns.items():
            match = re.search(pattern, question)
            if match:
                return extractor(match)
        
        return None
    
    @staticmethod
    def _extract_entities(question: str) -> Dict:
        """提取实体（列车编号、站点等）"""
        entities = {}
        
        # 列车编号 (如 JL0327, TRAIN35)
        train_pattern = r'([A-Z]{2}\d{4}|TRAIN\d+)'
        train_match = re.search(train_pattern, question, re.IGNORECASE)
        if train_match:
            entities['train_id'] = train_match.group(1)
        
        # 站点 (LMC, SHS, LOW, 罗湖, 上水, 低窝)
        station_keywords = {
            'LMC': ['lmc', '低窝', 'low'],
            'SHS': ['shs', '上水', 'sheung shui'],
            'LOW': ['low', '罗湖', 'lo wu']
        }
        
        for station, keywords in station_keywords.items():
            if any(kw in question.lower() for kw in keywords):
                entities['station'] = station
                break
        
        return entities
    
    @staticmethod
    def smart_retrieve(vector_db, question: str, n_results: int = 5) -> List[Dict]:
        """
        智能检索（根据问题类型优化检索策略）
        
        Args:
            vector_db: 向量数据库实例
            question: 用户问题
            n_results: 返回结果数
            
        Returns:
            检索到的文档列表
        """
        # 1. 分类问题
        classification = AdvancedRAG.classify_question(question)
        
        logger.info(f"✓ 问题分类: {classification['description']}")
        logger.info(f"  - 类型: {classification['type']}")
        logger.info(f"  - 报警类型: {classification['alarm_type']}")
        logger.info(f"  - 优先来源: {classification['priority_source']}")
        
        # 2. 构建增强的检索查询
        search_query = question
        
        # 如果识别到报警类型，用报警类型名称增强查询（提高相关性）
        if classification['alarm_type']:
            # 使用报警类型作为主要查询词
            alarm_type = classification['alarm_type']
            search_query = f"{alarm_type} {alarm_type} {question}"  # 重复两次增加权重
            logger.info(f"  增强查询: '{alarm_type}'")
        
        # 3. 执行检索（检索更多文档，然后过滤）
        all_docs = vector_db.search(search_query, n_results=min(20, n_results * 4))
        
        if not all_docs:
            logger.warning("未检索到任何文档")
            return []
        
        logger.info(f"✓ 初步检索到 {len(all_docs)} 个文档")
        
        # 4. 根据问题类型过滤和排序
        filtered_docs = AdvancedRAG._filter_and_rank_docs(
            all_docs, 
            classification, 
            n_results
        )
        
        logger.info(f"✓ 过滤后返回 {len(filtered_docs)} 个文档")
        
        # 显示文档来源
        sources = [doc.get('metadata', {}).get('source', 'unknown')[:30] 
                  for doc in filtered_docs[:3]]
        logger.info(f"✓ 使用文档: {sources}")
        
        return filtered_docs
    
    @staticmethod
    def _filter_and_rank_docs(
        docs: List[Dict], 
        classification: Dict, 
        n_results: int
    ) -> List[Dict]:
        """
        根据问题类型过滤和重新排序文档
        
        Args:
            docs: 原始文档列表
            classification: 问题分类结果
            n_results: 需要的结果数量
            
        Returns:
            过滤和排序后的文档列表
        """
        priority_source = classification.get('priority_source')
        alarm_type = classification.get('alarm_type')
        question_type = classification.get('type')
        
        # 1. 按文档类型分组
        work_instructions = []
        dal_logs = []
        
        for doc in docs:
            source_type = doc.get('metadata', {}).get('source_type', 'unknown')
            
            if source_type == 'work_instruction':
                work_instructions.append(doc)
            elif source_type == 'dal_log':
                dal_logs.append(doc)
        
        logger.info(f"  文档分布: Work Instructions={len(work_instructions)}, DAL Logs={len(dal_logs)}")
        
        # 2. 如果识别到报警类型，先按报警类型过滤（提高精确度）
        if alarm_type:
            logger.info(f"  第一步: 按报警类型 '{alarm_type}' 过滤")
            if work_instructions:
                work_instructions = AdvancedRAG._filter_by_alarm_type(work_instructions, alarm_type)
            if dal_logs:
                dal_logs = AdvancedRAG._filter_by_alarm_type(dal_logs, alarm_type)
            logger.info(f"  过滤后分布: WI={len(work_instructions)}, DAL={len(dal_logs)}")
        
        # 3. 根据问题类型决定使用哪些文档
        result_docs = []
        
        if question_type == 'procedure':
            # 操作流程：仅使用 Work Instructions
            result_docs = work_instructions[:n_results]
            logger.info(f"  → 操作流程问题，仅使用 Work Instructions")
            
        elif question_type in ['statistics', 'recent_event']:
            # 统计/最近事件：仅使用 DAL Logs
            result_docs = dal_logs[:n_results]
            logger.info(f"  → 历史查询问题，仅使用 DAL Logs")
            
        elif question_type == 'definition':
            # 定义解释：优先 Work Instructions，补充 DAL Logs
            result_docs = work_instructions[:max(n_results // 2, 3)]
            if len(result_docs) < n_results:
                result_docs.extend(dal_logs[:n_results - len(result_docs)])
            logger.info(f"  → 定义问题，混合使用（WI优先）")
            
        else:
            # 通用问题：根据优先级混合
            if priority_source == 'work_instruction':
                # 优先 Work Instructions
                result_docs = work_instructions[:max(n_results // 2, 3)]
                result_docs.extend(dal_logs[:n_results - len(result_docs)])
            elif priority_source == 'dal_log':
                # 优先 DAL Logs
                result_docs = dal_logs[:max(n_results // 2, 3)]
                result_docs.extend(work_instructions[:n_results - len(result_docs)])
            else:
                # 平衡混合
                half = n_results // 2
                result_docs = work_instructions[:half] + dal_logs[:half]
        
        return result_docs[:n_results]
    
    @staticmethod
    def _filter_by_alarm_type(docs: List[Dict], alarm_type: str) -> List[Dict]:
        """
        根据报警类型过滤文档（优先使用元数据）
        
        评分规则：
        1. metadata['alarm_type'] 完全匹配：20分（最高优先级）
        2. 文件名完全匹配报警类型：10分
        3. 文件名包含主要关键词：8分
        4. 文件名包含次要关键词：5分
        5. 内容包含关键词：1分
        """
        keywords = AdvancedRAG.ALARM_TYPE_KEYWORDS.get(alarm_type, [])
        
        if not keywords:
            return docs
        
        # 主关键词（完整的报警类型名称）
        primary_keyword = alarm_type
        # 次要关键词（其他相关词）
        secondary_keywords = [kw for kw in keywords if kw != alarm_type]
        
        # 为每个文档打分
        scored_docs = []
        
        for doc in docs:
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            source = metadata.get('source', '')
            doc_alarm_type = metadata.get('alarm_type', '')
            
            score = 0
            
            # 0. 检查元数据中的报警类型（最高优先级！）
            if doc_alarm_type and doc_alarm_type == alarm_type:
                score += 20
                logger.debug(f"    ✓ metadata['alarm_type'] 匹配 '{alarm_type}': {source}, 得分+20")
            
            # 1. 检查文件名（高优先级）
            if primary_keyword in source:
                score += 10
                logger.debug(f"    文件名完全匹配 '{primary_keyword}': {source}, 得分+10")
            else:
                # 检查次要关键词
                for kw in secondary_keywords:
                    if kw in source:
                        score += 5
                        logger.debug(f"    文件名包含 '{kw}': {source}, 得分+5")
                        break  # 只加一次
            
            # 2. 检查内容（低优先级）
            if primary_keyword in content:
                score += 3
            else:
                for kw in secondary_keywords[:2]:  # 只检查前2个次要关键词
                    if kw in content:
                        score += 1
                        break
            
            scored_docs.append((score, doc))
        
        # 按分数排序（降序）
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # 只保留得分>5的文档（排除只在内容中匹配的低分文档）
        filtered = [doc for score, doc in scored_docs if score >= 5]
        
        if filtered:
            top_scores = [score for score, _ in scored_docs[:5] if score >= 5]
            top_sources = [doc.get('metadata', {}).get('source', 'unknown')[:30] 
                          for _, doc in scored_docs[:3] if _ >= 5]
            logger.info(f"    报警类型过滤: 保留 {len(filtered)}/{len(docs)} 个文档")
            logger.info(f"    Top分数: {top_scores}, Top文档: {top_sources}")
            return filtered
        else:
            logger.warning(f"    报警类型过滤: 无高分匹配文档，返回原文档")
            return docs
    
    @staticmethod
    def build_enhanced_prompt(
        question: str, 
        docs: List[Dict], 
        classification: Dict
    ) -> str:
        """
        构建增强的提示词
        
        Args:
            question: 用户问题
            docs: 检索到的文档
            classification: 问题分类
            
        Returns:
            增强的提示词
        """
        question_type = classification['type']
        alarm_type = classification['alarm_type']
        
        # 构建上下文
        context_parts = []
        
        # 分别处理 Work Instructions 和 DAL Logs
        work_instructions = []
        dal_logs = []
        
        for doc in docs:
            source_type = doc.get('metadata', {}).get('source_type')
            content = doc.get('content', '')
            source = doc.get('metadata', {}).get('source', 'unknown')
            
            if source_type == 'work_instruction':
                work_instructions.append(f"【操作指南: {source}】\n{content}")
            elif source_type == 'dal_log':
                dal_logs.append(f"【历史记录】\n{content}")
        
        # 根据问题类型组织上下文
        if question_type == 'procedure':
            # 操作流程问题：只展示 Work Instructions
            context_parts.extend(work_instructions)
            context_header = "以下是相关的操作指南和规范流程："
            
        elif question_type in ['statistics', 'recent_event']:
            # 历史查询：只展示 DAL Logs
            context_parts.extend(dal_logs)
            context_header = "以下是相关的历史报警记录："
            
        else:
            # 混合问题：分别展示
            if work_instructions:
                context_parts.append("=== 操作指南 ===\n" + "\n\n".join(work_instructions))
            if dal_logs:
                context_parts.append("=== 历史记录 ===\n" + "\n\n".join(dal_logs[:3]))  # 限制DAL Logs数量
            context_header = "以下是相关的参考信息："
        
        context = "\n\n".join(context_parts)
        
        # 构建完整提示词
        prompt = f"""{context_header}

{context}

---

用户问题：{question}

请基于上述参考信息回答问题。"""
        
        if question_type == 'procedure':
            prompt += """

要求：
1. 如果有明确的操作步骤，请按步骤列出
2. 严格按照操作指南的内容回答
3. 不要添加文档中没有的内容"""
        
        elif question_type == 'statistics':
            prompt += """

要求：
1. 基于历史记录统计分析
2. 给出具体的数字和时间
3. 如果记录不完整，请说明"""
        
        return prompt


def test_advanced_rag():
    """测试高级 RAG（含领域相关性判断）"""
    test_questions = [
        # 专业问题（铁路相关）
        "列车超速应该如何处理？",
        "道岔故障如何处置？",
        "过去一个月发生了几次列车超速？",
        "JL0327最近的故障是什么？",
        "什么是ATS系统？",
        "请介绍一下道岔故障的处理流程",
        
        # 通用问题（非铁路相关）
        "北京交通大学简介",
        "请给我介绍一下北京交通大学",
        "什么是日内瓦国际发明展",
        "日内瓦国际发明展简介",
        "如何学习Python编程？",
        "什么是人工智能？"
    ]
    
    print("=" * 80)
    print("高级 RAG 智能问题分类测试（含领域相关性判断）")
    print("=" * 80)
    
    for i, question in enumerate(test_questions, 1):
        classification = AdvancedRAG.classify_question(question)
        
        print(f"\n【测试 {i}】问题: {question}")
        print(f"  类型: {classification['type']}")
        print(f"  报警类型: {classification['alarm_type']}")
        print(f"  领域相关: {classification.get('is_domain_relevant', False)}")
        print(f"  专业问题: {classification.get('is_professional', False)}")
        print(f"  → 应使用模式: {'专业模式（知识库）' if classification.get('is_professional') else '通用模式'}")
        print(f"  优先来源: {classification['priority_source']}")
        print(f"  描述: {classification['description']}")
        print("-" * 80)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_advanced_rag()

