"""
AI Assistant Flask Web 应用
提供 Web 界面和 API 服务
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS

from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, SECRET_KEY, DATA_DIR
from rag_system import RAGSystem
# from alarm_monitor import AlarmMonitor  # 已弃用：改用直接推送方式
from advanced_rag import AdvancedRAG
from precise_query import PreciseQuery

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)  # 启用跨域支持

# 初始化系统组件
rag_system = None
# alarm_monitor = None  # 已弃用：改用直接推送方式
precise_query = None  # 精确查询处理器
latest_alarms = []


def initialize_systems():
    """初始化系统组件"""
    global rag_system, precise_query  # alarm_monitor已移除
    
    try:
        logger.info("正在初始化 AI Assistant 系统...")
        
        # 初始化 RAG 系统
        rag_system = RAGSystem()
        logger.info("✓ RAG 系统初始化完成")
        
        # 初始化精确查询处理器
        dal_logs_dir = os.path.join(DATA_DIR, 'dal_logs')
        precise_query = PreciseQuery(dal_logs_dir)
        logger.info("✓ 精确查询处理器初始化完成")
        
        # 已移除：报警监控（改用EYES-T直接推送方式）
        # alarm_monitor = AlarmMonitor()
        # alarm_monitor.register_callback(on_new_alarm)
        # alarm_monitor.start()
        logger.info("✓ 报警监控已改用直接推送方式（无需从CSV读取）")
        
        logger.info("✓ AI Assistant 系统初始化成功")
        return True
        
    except Exception as e:
        logger.error(f"系统初始化失败: {e}")
        return False


# 已弃用：on_new_alarm回调函数（改用/api/alarms/push直接推送）
# def on_new_alarm(alarm_data: dict):
#     """新报警回调函数"""
#     global latest_alarms
#     
#     # 使用 RAG 系统分析报警
#     try:
#         analysis_result = rag_system.analyze_alarm(alarm_data)
#         alarm_data['ai_analysis'] = analysis_result.get('analysis', '')
#         alarm_data['work_instructions'] = analysis_result.get('work_instructions', [])
#     except Exception as e:
#         logger.error(f"报警分析失败: {e}")
#         alarm_data['ai_analysis'] = '分析失败'
#     
#     # 添加到最新报警列表
#     latest_alarms.insert(0, alarm_data)
#     # 保持列表不超过2000条（支持大量报警显示）
#     if len(latest_alarms) > 2000:
#         latest_alarms = latest_alarms[:2000]
#     
#     logger.info(f"新报警已处理: {alarm_data.get('alarm_type', 'Unknown')}")


# ==================== Web 路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """获取系统状态"""
    try:
        status = rag_system.get_system_status()
        # alarm_summary = alarm_monitor.get_alarm_summary()  # 已弃用
        alarm_summary = {
            'total': len(latest_alarms),
            'by_type': {},
            'by_station': {}
        }
        # 统计报警类型
        for alarm in latest_alarms:
            alarm_type = alarm.get('alarm_type', 'Unknown')
            alarm_summary['by_type'][alarm_type] = alarm_summary['by_type'].get(alarm_type, 0) + 1
        
        return jsonify({
            'success': True,
            'data': {
                'system': status,
                'alarms': alarm_summary,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """对话接口（支持模式选择）- 非流式模式"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        mode = data.get('mode', 'auto')  # auto, strict, general
        
        if not question:
            return jsonify({
                'success': False,
                'error': '问题不能为空'
            }), 400
        
        # 使用 RAG 系统查询（支持模式参数）
        result = rag_system.query(question, use_history=True, mode=mode)
        
        return jsonify({
            'success': True,
            'data': {
                'answer': result['answer'],
                'sources': result.get('sources', []),
                'mode': result.get('mode', mode),  # 返回实际使用的模式
                'timestamp': result.get('timestamp', datetime.now().isoformat())
            }
        })
        
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chat/stream', methods=['POST'])
def api_chat_stream():
    """流式对话接口（边生成边返回）"""
    try:
        from flask import Response, stream_with_context
        import json
        
        data = request.get_json()
        question = data.get('question', '').strip()
        mode = data.get('mode', 'auto')
        
        if not question:
            return jsonify({
                'success': False,
                'error': '问题不能为空'
            }), 400
        
        def generate():
            """生成器函数，逐块返回响应"""
            try:
                # 1. 先返回开始标记
                yield f"data: {json.dumps({'type': 'start', 'mode': mode})}\n\n"
                
                # 2. 智能判断问题类型（用于 auto 模式）
                classification = AdvancedRAG.classify_question(question)
                logger.info(f"✓ 问题分类: {classification['description']}")
                logger.info(f"  类型: {classification['type']}, 报警: {classification.get('alarm_type', 'None')}")
                logger.info(f"  领域相关: {classification.get('is_domain_relevant', False)}, 专业问题: {classification.get('is_professional', False)}")
                
                # 3. 根据模式决定是否检索文档
                if mode == 'strict':
                    # 专业模式：强制使用知识库
                    should_use_kb = True
                    actual_mode = "strict"
                    logger.info("✓ 专业模式：强制使用知识库")
                elif mode == 'auto':
                    # 智能模式：根据问题分类自动决定（使用新的两级分类结果）
                    if classification.get('is_professional', False):
                        should_use_kb = True
                        actual_mode = "strict"
                        logger.info(f"✓ 智能模式：检测到专业问题，自动切换到知识库模式")
                    else:
                        should_use_kb = False
                        actual_mode = "general"
                        logger.info(f"✓ 智能模式：检测到通用问题，使用通用模式")
                else:
                    # 通用模式：不使用知识库
                    should_use_kb = False
                    actual_mode = "general"
                    logger.info("⊙ 通用模式：不使用知识库")
                
                # 4. 如果需要使用知识库，执行检索
                precise_results = None  # 精确查询结果
                
                if should_use_kb:
                    # 【新增】检查是否需要精确查询（时间敏感、统计类）
                    if precise_query and PreciseQuery.should_use_precise_query(question, classification):
                        logger.info("⚡ 检测到需要精确查询，执行结构化查询...")
                        
                        # 提取查询参数
                        params = PreciseQuery.extract_query_params(question, classification)
                        
                        # 执行精确查询
                        if classification['type'] in ['statistics']:
                            # 统计类问题
                            precise_results = precise_query.query_alarm_count(
                                station=params.get('station'),
                                alarm_type=params.get('alarm_type'),
                                year=params.get('year'),
                                month=params.get('month')
                            )
                            logger.info(f"✓ 精确统计: 共 {precise_results['count']} 条记录")
                        
                        elif classification['type'] in ['recent_event']:
                            # 最近/最早事件问题
                            order = params.get('order', 'latest')  # 默认最新
                            order_label = "最早" if order == 'earliest' else "最新"
                            precise_results = precise_query.query_latest_alarms(
                                station=params.get('station'),
                                alarm_type=params.get('alarm_type'),
                                limit=10,
                                order=order
                            )
                            logger.info(f"✓ 精确查询: 返回 {len(precise_results) if isinstance(precise_results, list) else 0} 条{order_label}记录")
                        
                        # 如果精确查询有结果，直接使用，不再做向量检索
                        if precise_results:
                            retrieved_docs = None  # 不使用向量检索结果
                            logger.info("✓ 使用精确查询结果，跳过向量检索")
                        else:
                            logger.warning("⚠️ 精确查询无结果，降级到向量检索")
                    
                    # 如果没有使用精确查询，或精确查询无结果，使用向量检索
                    if not precise_results:
                        # 使用高级 RAG 进行智能检索
                        retrieved_docs = AdvancedRAG.smart_retrieve(
                            rag_system.vector_db, 
                            question, 
                            n_results=5
                        )
                        
                        # 提取文档内容
                        doc_contents = []
                        if retrieved_docs and isinstance(retrieved_docs, list):
                            for doc in retrieved_docs:
                                content = doc.get('content', '')
                                if content and content.strip():
                                    doc_contents.append(content)
                        
                        logger.info(f"✓ 提取到 {len(doc_contents)} 个有效文档片段")
                        
                        # 如果没有检索到文档，降级到通用模式
                        if len(doc_contents) == 0:
                            actual_mode = "general"
                            retrieved_docs = None
                            logger.warning("⚠️ 未检索到文档，降级到通用模式")
                else:
                    # 不使用知识库
                    retrieved_docs = None
                
                yield f"data: {json.dumps({'type': 'mode', 'mode': actual_mode})}\n\n"
                
                # 3. 构建消息
                history = rag_system.conversation_history if rag_system else []
                
                if actual_mode == "general":
                    # 通用模式
                    messages = [
                        {"role": "system", "content": "你是一个专业、友好、有帮助的 AI 助手。你可以回答各种问题，提供准确的信息和建议。"}
                    ]
                    if history:
                        messages.extend(history)
                    messages.append({"role": "user", "content": question})
                else:
                    # 严格模式：基于知识库
                    
                    # 【新增】优先使用精确查询结果
                    if precise_results:
                        logger.info("📊 使用精确查询结果构建上下文")
                        
                        # 根据问题类型构建上下文
                        if classification['type'] == 'statistics':
                            # 统计类问题
                            count = precise_results['count']
                            records = precise_results['records']
                            
                            context = f"=== 精确统计结果 ===\n\n"
                            context += f"**总计：{count} 条记录**（这是精确统计的结果，请务必在回答中使用这个数字）\n\n"
                            context += f"**详细记录（共 {len(records)} 条，按时间降序）：**\n"
                            for i, record in enumerate(records, 1):
                                context += f"{i}. {record['timestamp']} | {record['station']} | {record['alarm_type']} | {record['description']} | 严重程度:{record['severity']}\n"
                            
                            if len(records) < count:
                                context += f"\n注意：以上仅显示前 {len(records)} 条记录，实际共有 {count} 条。\n"
                            
                            system_prompt = f"""你是 EYES-T 系统的数据分析助手。

【重要】你正在回答统计类问题，必须严格遵守以下规则：

1. **总数必须准确**：系统已精确统计，总数为 {count} 条，你的回答中必须使用这个数字
2. **列出所有记录**：上面提供了 {len(records)} 条详细记录，你必须在回答中列出所有这些记录，不能遗漏
3. **不要推测**：只使用提供的数据，不要添加任何数据中没有的信息
4. **格式清晰**：先说明总数，再逐条列出所有记录

错误示例：说总数是{count}条，但只列出了{len(records)-1}条
正确示例：说总数是{count}条，并完整列出所有{len(records)}条记录"""
                        
                        elif classification['type'] == 'recent_event':
                            # 最近事件问题
                            if isinstance(precise_results, list) and precise_results:
                                latest_record = precise_results[0]  # 第一条就是最新的
                                context = "=== 最新报警记录（已按时间降序排列） ===\n\n"
                                context += f"**最新记录（第1条）：**\n"
                                context += f"时间：{latest_record['timestamp']}\n"
                                context += f"车站：{latest_record['station']}\n"
                                context += f"类型：{latest_record['alarm_type']}\n"
                                context += f"描述：{latest_record['description']}\n"
                                context += f"严重程度：{latest_record['severity']}\n\n"
                                
                                if len(precise_results) > 1:
                                    context += f"**近期其他记录（共{len(precise_results)-1}条）：**\n"
                                    for i, record in enumerate(precise_results[1:], 2):
                                        context += f"{i}. {record['timestamp']} | {record['station']} | {record['alarm_type']} | {record['description']}\n"
                                
                                system_prompt = f"""你是 EYES-T 系统的数据分析助手。

【重要】你正在回答"最近/最新"相关的问题，必须严格遵守：

1. **最新记录**：上面第1条记录（时间：{latest_record['timestamp']}）就是最新的，这是系统精确查询并按时间降序排列的结果
2. **准确引用**：回答时必须使用第1条记录的准确信息（时间、车站、类型、描述）
3. **不要推测**：只使用提供的数据，不要说"可能"、"大概"等不确定的词
4. **时间最近**：用户问的是"最近"或"最新"，答案就是第1条记录，不要回答其他更早的记录"""
                            else:
                                context = "未找到相关记录"
                                system_prompt = "你是 EYES-T 系统助手"
                        else:
                            context = str(precise_results)
                            system_prompt = "你是 EYES-T 系统助手，基于提供的数据准确回答问题。"
                        
                        logger.info(f"✓ 精确查询上下文已构建，长度: {len(context)} 字符")
                        
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"{context}\n\n---\n\n用户问题：{question}\n\n请严格基于上述数据回答问题，不要添加或推测任何数据中没有的信息。"}
                        ]
                    
                    # 如果没有精确查询结果，使用向量检索结果
                    elif not retrieved_docs:
                        logger.error("❌ 未检索到文档！")
                        messages = [
                            {"role": "system", "content": "你是 EYES-T 系统助手"},
                            {"role": "user", "content": f"（知识库为空）用户问题：{question}"}
                        ]
                    else:
                        # 使用高级 RAG 构建增强提示词（向量检索）
                        classification = AdvancedRAG.classify_question(question)
                        
                        # 构建分类上下文
                        work_instructions = []
                        dal_logs = []
                        
                        for doc in retrieved_docs:
                            source_type = doc.get('metadata', {}).get('source_type')
                            content = doc.get('content', '')
                            source = doc.get('metadata', {}).get('source', 'unknown')
                            
                            if source_type == 'work_instruction':
                                work_instructions.append(f"【操作指南: {source}】\n{content}")
                            elif source_type == 'dal_log':
                                dal_logs.append(f"【历史记录】\n{content}")
                        
                        logger.info(f"  上下文组成: WI={len(work_instructions)}, DAL={len(dal_logs)}")
                        
                        # 根据问题类型组织上下文
                        if classification['type'] == 'procedure':
                            # 操作流程：仅用 Work Instructions
                            context = "以下是相关的操作指南和规范流程：\n\n" + "\n\n".join(work_instructions[:5])
                            system_prompt = """你是 EYES-T 轨道交通监控系统的专业助手。

你的职责：
1. 严格按照提供的操作指南回答问题
2. 如果有明确的操作步骤，请按步骤列出
3. 不要添加操作指南中没有的内容
4. 保持专业、准确、详细"""
                            
                        elif classification['type'] in ['statistics', 'recent_event']:
                            # 历史查询：仅用 DAL Logs
                            context = "以下是相关的历史报警记录：\n\n" + "\n\n".join(dal_logs[:5])
                            system_prompt = """你是 EYES-T 系统的数据分析助手。

你的职责：
1. 基于历史记录进行统计分析
2. 给出具体的数字和时间
3. 如果记录不完整，请明确说明"""
                            
                        else:
                            # 混合使用
                            context_parts = []
                            if work_instructions:
                                context_parts.append("=== 操作指南 ===\n" + "\n\n".join(work_instructions[:3]))
                            if dal_logs:
                                context_parts.append("=== 历史记录 ===\n" + "\n\n".join(dal_logs[:2]))
                            context = "\n\n".join(context_parts)
                            system_prompt = "你是 EYES-T 系统助手，基于提供的文档准确回答问题。"
                        
                        logger.info(f"✓ 上下文已构建，长度: {len(context)} 字符")
                        
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"{context}\n\n---\n\n用户问题：{question}\n\n请基于上述参考信息回答问题。"}
                        ]
                
                # 4. 流式生成回答
                full_answer = ""
                for chunk in rag_system.llm_client.chat_stream(messages):
                    full_answer += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                
                # 5. 更新对话历史
                rag_system.conversation_history.append({"role": "user", "content": question})
                rag_system.conversation_history.append({"role": "assistant", "content": full_answer})
                
                # 限制历史长度
                from config import MAX_CONVERSATION_HISTORY
                if len(rag_system.conversation_history) > MAX_CONVERSATION_HISTORY * 2:
                    rag_system.conversation_history = rag_system.conversation_history[-MAX_CONVERSATION_HISTORY * 2:]
                
                # 6. 返回完成标记
                yield f"data: {json.dumps({'type': 'done', 'timestamp': datetime.now().isoformat()})}\n\n"
                
            except Exception as e:
                logger.error(f"流式对话生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        logger.error(f"流式对话处理失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/alarms/latest')
def api_latest_alarms():
    """获取最新报警（按类型分类）"""
    try:
        count = request.args.get('count', 500, type=int)  # 默认500条，支持更多报警显示
        alarm_type = request.args.get('type', 'all')  # all, alarmlist, turnout, train, power, route_check
        
        if alarm_type == 'all':
            alarms = latest_alarms[:count]
        else:
            # 根据类型过滤报警
            alarms = [a for a in latest_alarms if a.get('alarm_type', '').lower() == alarm_type.lower()][:count]
        
        return jsonify({
            'success': True,
            'data': {
                'alarms': alarms,
                'total': len(alarms),
                'type': alarm_type
            }
        })
    except Exception as e:
        logger.error(f"获取最新报警失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/alarms/push', methods=['POST'])
def api_push_alarm():
    """接收EYES-T系统实时推送的报警数据"""
    global latest_alarms
    
    try:
        data = request.get_json()
        alarm_type = data.get('alarm_type', 'Unknown')
        alarm_data = data.get('data', {})
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        # 构建统一格式的报警记录
        alarm_record = {
            'alarm_type': alarm_type,
            'timestamp': timestamp,
            'detected_time': timestamp,
            **alarm_data  # 包含所有原始数据
        }
        
        # 添加到最新报警列表（头部插入）
        latest_alarms.insert(0, alarm_record)
        
        # 保持列表不超过2000条（支持大量报警显示）
        if len(latest_alarms) > 2000:
            latest_alarms = latest_alarms[:2000]
        
        logger.info(f"✓ 接收到实时报警: {alarm_type}")
        
        return jsonify({
            'success': True,
            'message': 'Alarm received'
        })
        
    except Exception as e:
        logger.error(f"接收报警数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/alarms/summary')
def api_alarm_summary():
    """获取报警摘要"""
    try:
        # 从latest_alarms直接统计（不再从CSV读取）
        summary = {
            'total': len(latest_alarms),
            'by_type': {},
            'by_station': {}
        }
        
        for alarm in latest_alarms:
            # 统计类型
            alarm_type = alarm.get('alarm_type', 'Unknown')
            summary['by_type'][alarm_type] = summary['by_type'].get(alarm_type, 0) + 1
            
            # 统计站点（如果有）
            station = alarm.get('station') or alarm.get('area')
            if station and station != 'N/A':
                summary['by_station'][station] = summary['by_station'].get(station, 0) + 1
        
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        logger.error(f"获取报警摘要失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/alarms/analyze', methods=['POST'])
def api_analyze_alarm():
    """分析特定报警"""
    try:
        data = request.get_json()
        alarm_data = data.get('alarm_data', {})
        
        if not alarm_data:
            return jsonify({
                'success': False,
                'error': '报警数据不能为空'
            }), 400
        
        # 分析报警
        result = rag_system.analyze_alarm(alarm_data)
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"分析报警失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/alarms/frequency', methods=['POST'])
def api_alarm_frequency():
    """查询报警频率"""
    try:
        data = request.get_json()
        alarm_type = data.get('alarm_type')
        station = data.get('station')
        days = data.get('days', 30)
        
        result = rag_system.query_alarm_frequency(
            alarm_type=alarm_type,
            station=station,
            days=days
        )
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"查询报警频率失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/instructions/<alarm_type>')
def api_get_instructions(alarm_type):
    """获取处置指令"""
    try:
        station = request.args.get('station')
        instructions = rag_system.get_处置建议(alarm_type, station)
        
        return jsonify({
            'success': True,
            'data': {
                'alarm_type': alarm_type,
                'station': station,
                'instructions': instructions
            }
        })
        
    except Exception as e:
        logger.error(f"获取处置指令失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/knowledge/init', methods=['POST'])
def api_init_knowledge():
    """初始化知识库"""
    try:
        data = request.get_json() or {}
        reload = data.get('reload', False)
        
        stats = rag_system.initialize_knowledge_base(reload=reload)
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"初始化知识库失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/conversation/clear', methods=['POST'])
def api_clear_conversation():
    """清空对话历史"""
    try:
        rag_system.clear_conversation_history()
        
        return jsonify({
            'success': True,
            'message': '对话历史已清空'
        })
        
    except Exception as e:
        logger.error(f"清空对话历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'API 接口不存在'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"内部服务器错误: {error}")
    return jsonify({
        'success': False,
        'error': '内部服务器错误'
    }), 500


# ==================== 主函数 ====================

def main():
    """主函数"""
    print("=" * 70)
    print(" " * 20 + "EYES-T AI Assistant")
    print("=" * 70)
    print()
    
    # 初始化系统
    if not initialize_systems():
        print("✗ 系统初始化失败，请检查配置")
        return
    
    print(f"\n✓ AI Assistant 系统已启动")
    print(f"✓ Web 界面地址: http://{FLASK_HOST}:{FLASK_PORT}")
    print(f"✓ 报警监控: 已启动")
    print(f"✓ RAG 系统: 已就绪")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 70)
    print()
    
    try:
        # 启动 Flask 应用
        app.run(
            host=FLASK_HOST,
            port=FLASK_PORT,
            debug=FLASK_DEBUG,
            use_reloader=False  # 禁用重载器以避免重复初始化
        )
    except KeyboardInterrupt:
        print("\n\n正在关闭系统...")
        # if alarm_monitor:  # 已移除
        #     alarm_monitor.stop()
        print("✓ 系统已关闭")
    except Exception as e:
        logger.error(f"应用运行错误: {e}")
        print(f"✗ 错误: {e}")


if __name__ == '__main__':
    main()

