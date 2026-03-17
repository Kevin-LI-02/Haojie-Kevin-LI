# 🚀 MTR EyesT OCR系统 - 性能监控系统使用指南

## 📋 概述

完整版性能监控系统已集成到所有四个检测界面，实时监控系统性能并生成详细报告。

## 📊 监控的性能指标

### 1. **核心性能指标** ⭐
- **OCR处理时间**: 单次OCR识别耗时（毫秒）
- **总处理周期**: 一帧完整处理时间（毫秒）
- **实际FPS**: 每秒处理帧数
- **当前FPS**: 实时帧率

### 2. **资源使用指标** 💻
- **GPU利用率**: GPU使用百分比
- **GPU显存**: 显存占用（MB）
- **CPU利用率**: CPU使用百分比  
- **内存使用**: RAM占用（MB）

### 3. **统计指标** 📈
- **OCR成功率**: 成功识别百分比
- **总帧数**: 捕获的总帧数
- **处理帧数**: 实际处理的帧数
- **运行时间**: 持续运行时长

## 🛠️ 如何使用

### 步骤 1: 安装依赖（可选，用于GPU监控）

```bash
pip install gputil
```

> **注意**: 如果不安装 GPUtil，系统仍可正常工作，但GPU监控功能将被禁用。

### 步骤 2: 运行检测系统

启动任意检测界面（Train/Turnout/Power/AlarmList），性能监控会自动开始。

### 步骤 3: 查看实时性能数据

性能数据每 **2秒** 自动打印到控制台：

```
🚄 列车检测性能监控
━━━━━━━━━━━━━━━━━━━━━━━━
📊 OCR: 85.3ms | 总: 142.1ms | FPS: 7.2
💻 CPU: 38.5% | 内存: 856MB
🎮 GPU: 45.2% | 显存: 1024MB
📈 成功率: 98.5% | 运行: 00:15:32
```

### 步骤 4: 停止检测保存日志

当点击"停止检测"按钮时，系统会自动：
1. 在控制台打印完整的性能摘要
2. 保存性能日志到 `performance_logs/` 文件夹

### 步骤 5: 生成汇总报告

运行报告生成工具：

```bash
python generate_performance_report.py
```

或在Python中调用：

```python
from generate_performance_report import generate_performance_report
generate_performance_report()
```

报告将保存在 `performance_logs/performance_summary_report.txt`

## 📁 文件结构

```
Code-2025.11.7_GPU/
├── performance_monitor.py              # 性能监控核心模块
├── generate_performance_report.py      # 报告生成工具
├── train.py                           # 列车检测（已集成）
├── turnout.py                         # 道岔检测（已集成）
├── power.py                           # 电源检测（已集成）
├── alarmlist.py                       # 告警列表（已集成）
└── performance_logs/                  # 性能日志文件夹
    ├── Train Detection_performance_20231126_143022.csv
    ├── Turnout Detection_performance_20231126_143155.csv
    ├── Power Detection_performance_20231126_143310.csv
    ├── AlarmList Detection_performance_20231126_143445.csv
    └── performance_summary_report.txt  # 汇总报告
```

## 📈 性能评级标准

### OCR处理时间
- **优秀** ⭐⭐⭐⭐⭐: < 50ms
- **良好** ⭐⭐⭐⭐: 50-100ms
- **一般** ⭐⭐⭐: 100-150ms
- **需优化** ⭐⭐: > 150ms

### FPS（帧率）
- **优秀** ⭐⭐⭐⭐⭐: ≥ 10 fps
- **良好** ⭐⭐⭐⭐: 6-10 fps
- **一般** ⭐⭐⭐: 3-6 fps
- **需优化** ⭐⭐: < 3 fps

### GPU使用率
- **优秀** ⭐⭐⭐⭐⭐: 30-60% （利用合理）
- **良好** ⭐⭐⭐⭐: < 30% （利用偏低）
- **一般** ⭐⭐⭐: 60-80% （利用偏高）
- **需优化** ⭐⭐: > 80% （利用过高）

## 🎯 优化建议

根据性能监控结果，可以采取以下优化措施：

### 如果 OCR 处理时间过长
1. 检查GPU是否正常工作
2. 减小检测区域大小
3. 调整图像预处理参数

### 如果 FPS 过低
1. 增加跳帧数（frame_skip）
2. 优化OCR区域配置
3. 减少同时检测的区域数量

### 如果 GPU 使用率过低
1. 检查CUDA配置
2. 确认PaddleOCR正确使用GPU
3. 考虑增加批处理大小

### 如果 GPU 使用率过高
1. 减少检测频率
2. 优化并行任务数量
3. 考虑使用更高性能的GPU

## 🔍 示例输出

### 实时监控输出示例

```
🚄 列车检测性能监控
━━━━━━━━━━━━━━━━━━━━━━━━
📊 OCR: 85.3ms | 总: 142.1ms | FPS: 7.2
💻 CPU: 38.5% | 内存: 856MB
🎮 GPU: 45.2% | 显存: 1024MB
📈 成功率: 98.5% | 运行: 00:15:32
```

### 完整性能摘要示例

```
╔═══════════════════════════════════════════════════════════╗
║  性能监控 - Train Detection                          
╠═══════════════════════════════════════════════════════════╣
║  📊 核心性能指标                                           
║    • OCR处理时间: 85.32 ms (平均)
║    • 总处理时间: 142.15 ms (平均)
║    • 当前FPS: 7.18 | 平均FPS: 7.05
║                                                             
║  💻 资源使用                                               
║    • CPU使用率: 38.5%
║    • 内存使用: 856.2 MB
║    • GPU使用率: 45.2%
║    • GPU显存: 1024 MB
║                                                             
║  📈 统计信息                                               
║    • 总帧数: 6543 | 处理帧数: 654
║    • OCR成功: 644 | 失败: 10
║    • OCR成功率: 98.5%
║    • 运行时间: 00:15:32
╚═══════════════════════════════════════════════════════════╝
```

## 🔧 API 参考

### PerformanceMonitor 类

```python
from performance_monitor import PerformanceMonitor

# 创建监控器
monitor = PerformanceMonitor(module_name="My Module", enable_gpu_monitor=True)

# 开始计时
start_time = monitor.start_timer()

# OCR 处理
# ... your OCR code ...

# 记录 OCR 时间
ocr_time = monitor.record_ocr_time(start_time)

# 记录总处理时间
total_time = monitor.record_total_time(start_time)

# 记录一帧完成
monitor.record_frame(ocr_success=True)

# 更新系统指标
monitor.update_system_metrics()

# 获取当前统计
stats = monitor.get_current_stats()

# 打印摘要
monitor.print_summary()

# 保存日志
monitor.save_performance_log()
```

## 📞 支持

如有问题或建议，请联系开发团队。

---

**版本**: 1.0.0  
**更新日期**: 2024-11-26  
**作者**: MTR EyesT Development Team




