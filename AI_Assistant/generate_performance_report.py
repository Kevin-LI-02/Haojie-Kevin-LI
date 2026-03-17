# generate_performance_report.py
# 性能监控汇总报告生成工具
#
# 功能说明：
# 本工具从各个模块的性能日志CSV文件中读取性能指标，生成汇总报告
# 性能日志由 performance_monitor.py 在各模块运行时自动生成
# 日志文件格式：{模块名}_performance_{时间戳}.csv
# 日志文件位置：performance_logs/{模块名}/

import os
import csv
import glob
from datetime import datetime

def generate_performance_report(
    performance_logs_folder="performance_logs",
    output_file=None,
    output_csv_file=None,
):
    """
    生成性能监控汇总报告
    
    Args:
        performance_logs_folder: 性能日志文件夹路径
        output_file: 输出报告文件名（如果为None，将自动生成带时间戳的文件名）
        output_csv_file: 输出CSV文件名（如果为None，将自动生成带时间戳的文件名）
    """
    
    if not os.path.exists(performance_logs_folder):
        print(f"❌ 性能日志文件夹不存在: {performance_logs_folder}")
        return
    
    # 创建汇总报告专用文件夹
    reports_folder = os.path.join(performance_logs_folder, "reports")
    os.makedirs(reports_folder, exist_ok=True)
    
    # 生成带日期时间戳的文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if output_file is None:
        output_file = f"performance_summary_report_{timestamp}.txt"
    if output_csv_file is None:
        output_csv_file = f"performance_summary_report_{timestamp}.csv"
    
    # 查找所有性能日志CSV文件（含子目录）
    log_files = glob.glob(
        os.path.join(performance_logs_folder, "**", "*_performance_*.csv"),
        recursive=True,
    )
    
    if not log_files:
        print(f"❌ 未找到性能日志文件: {performance_logs_folder}")
        return
    
    print(f"✅ 找到 {len(log_files)} 个性能日志文件")
    
    # 按模块分组
    modules_data = {}
    
    for log_file in log_files:
        module_name = os.path.basename(log_file).split('_performance_')[0]
        
        # 读取CSV文件
        data = {}
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # 跳过表头
                for row in reader:
                    if len(row) >= 2:
                        data[row[0]] = row[1]
        except Exception as e:
            print(f"⚠️  读取文件失败: {log_file}, 错误: {e}")
            continue
        
        if module_name not in modules_data:
            modules_data[module_name] = []
        modules_data[module_name].append((log_file, data))
    
    # 生成报告
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("           MTR EyesT OCR系统 - 性能监控汇总报告")
    report_lines.append("=" * 80)
    report_lines.append(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"分析日志数量: {len(log_files)} 个")
    report_lines.append(f"涉及模块数量: {len(modules_data)} 个")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # 各模块详细报告
    module_summaries = []  # 用于CSV输出
    for module_name, logs in modules_data.items():
        report_lines.append(f"\n{'─' * 80}")
        report_lines.append(f"📊 模块: {module_name.upper()}")
        report_lines.append(f"{'─' * 80}")
        
        # 汇总所有日志的数据（单位框耗时 & 平均OCR处理时间）
        all_unit_box_times = []
        all_ocr_times = []
        all_total_times = []
        all_fps = []
        all_cpu = []
        all_memory = []
        all_gpu_util = []
        all_gpu_memory = []
        all_success_rates = []
        all_runtimes = []
        
        for log_file, data in logs:
            filename = os.path.basename(log_file)
            report_lines.append(f"\n  📄 文件: {filename}")
            
            # 提取关键指标
            if '单位框耗时' in data:
                all_unit_box_times.append(float(data['单位框耗时']))
            if '平均OCR处理时间' in data:
                all_ocr_times.append(float(data['平均OCR处理时间']))
            if '平均总处理时间' in data:
                all_total_times.append(float(data['平均总处理时间']))
            if '平均FPS' in data:
                all_fps.append(float(data['平均FPS']))
            if '平均CPU使用率' in data:
                all_cpu.append(float(data['平均CPU使用率']))
            if '平均内存使用' in data:
                all_memory.append(float(data['平均内存使用']))
            if '平均GPU使用率' in data:
                all_gpu_util.append(float(data['平均GPU使用率']))
            if '平均GPU显存' in data:
                all_gpu_memory.append(float(data['平均GPU显存']))
            if 'OCR成功率' in data:
                all_success_rates.append(float(data['OCR成功率']))
            if '运行时间' in data:
                all_runtimes.append(float(data['运行时间']))
            
            # 显示关键指标
            report_lines.append(f"    • 单位框耗时: {data.get('单位框耗时', 'N/A')} ms/框")
            report_lines.append(f"    • 平均OCR处理时间: {data.get('平均OCR处理时间', 'N/A')} ms")
            report_lines.append(f"    • 总处理时间: {data.get('平均总处理时间', 'N/A')} ms")
            report_lines.append(f"    • 平均FPS: {data.get('平均FPS', 'N/A')}")
            report_lines.append(f"    • CPU使用率: {data.get('平均CPU使用率', 'N/A')}%")
            report_lines.append(f"    • 内存使用: {data.get('平均内存使用', 'N/A')} MB")
            report_lines.append(f"    • GPU使用率: {data.get('平均GPU使用率', 'N/A')}%")
            report_lines.append(f"    • GPU显存: {data.get('平均GPU显存', 'N/A')} MB")
            report_lines.append(f"    • OCR成功率: {data.get('OCR成功率', 'N/A')}%")
            report_lines.append(f"    • 运行时间: {data.get('运行时间(格式化)', 'N/A')}")
        
        # 模块汇总统计
        if all_total_times:
            avg_unit_box = sum(all_unit_box_times) / len(all_unit_box_times) if all_unit_box_times else None
            avg_ocr = sum(all_ocr_times) / len(all_ocr_times) if all_ocr_times else None
            avg_total = sum(all_total_times) / len(all_total_times)
            avg_fps = sum(all_fps) / len(all_fps)
            avg_cpu = sum(all_cpu) / len(all_cpu)
            avg_mem = sum(all_memory) / len(all_memory)
            avg_gpu_util = sum(all_gpu_util) / len(all_gpu_util) if all_gpu_util else None
            avg_gpu_mem = sum(all_gpu_memory) / len(all_gpu_memory) if all_gpu_memory else None
            avg_success = sum(all_success_rates) / len(all_success_rates) if all_success_rates else None
            total_runtime = sum(all_runtimes) if all_runtimes else None

            report_lines.append(f"\n  📈 {module_name} 模块汇总统计:")
            if avg_unit_box is not None:
                report_lines.append(f"    • 单位框耗时: {avg_unit_box:.2f} ms/框")
            if avg_ocr is not None:
                report_lines.append(f"    • 平均OCR处理时间: {avg_ocr:.2f} ms")
            report_lines.append(f"    • 平均总处理时间: {avg_total:.2f} ms")
            report_lines.append(f"    • 平均FPS: {avg_fps:.2f}")
            report_lines.append(f"    • 平均CPU使用率: {avg_cpu:.2f}%")
            report_lines.append(f"    • 平均内存使用: {avg_mem:.2f} MB")
            if avg_gpu_util is not None:
                report_lines.append(f"    • 平均GPU使用率: {avg_gpu_util:.2f}%")
                report_lines.append(f"    • 平均GPU显存: {avg_gpu_mem:.2f} MB")
            if avg_success is not None:
                report_lines.append(f"    • 平均OCR成功率: {avg_success:.2f}%")
            if total_runtime is not None:
                hours = int(total_runtime // 3600)
                minutes = int((total_runtime % 3600) // 60)
                seconds = int(total_runtime % 60)
                report_lines.append(f"    • 累计运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}")

            module_summaries.append(
                {
                    "module": module_name,
                    "avg_unit_box_ms": f"{avg_unit_box:.2f}" if avg_unit_box is not None else "",
                    "avg_ocr_ms": f"{avg_ocr:.2f}" if avg_ocr is not None else "",
                    "avg_total_ms": f"{avg_total:.2f}",
                    "avg_fps": f"{avg_fps:.2f}",
                    "avg_cpu_percent": f"{avg_cpu:.2f}",
                    "avg_mem_mb": f"{avg_mem:.2f}",
                    "avg_gpu_util_percent": f"{avg_gpu_util:.2f}" if avg_gpu_util is not None else "",
                    "avg_gpu_mem_mb": f"{avg_gpu_mem:.2f}" if avg_gpu_mem is not None else "",
                    "avg_success_rate_percent": f"{avg_success:.2f}" if avg_success is not None else "",
                    "total_runtime_seconds": f"{total_runtime:.2f}" if total_runtime is not None else "",
                }
            )
    
    # 全局汇总
    report_lines.append(f"\n\n{'═' * 80}")
    report_lines.append("🎯 全局性能评估")
    report_lines.append(f"{'═' * 80}")
    
    # 计算所有模块的平均值（单位框耗时 & 平均OCR处理时间）
    all_modules_unit_box = []
    all_modules_ocr = []
    all_modules_total = []
    all_modules_fps = []
    all_modules_cpu = []
    all_modules_memory = []
    all_modules_gpu_util = []
    all_modules_gpu_memory = []
    
    for module_name, logs in modules_data.items():
        for log_file, data in logs:
            if '单位框耗时' in data:
                all_modules_unit_box.append(float(data['单位框耗时']))
            if '平均OCR处理时间' in data:
                all_modules_ocr.append(float(data['平均OCR处理时间']))
            if '平均总处理时间' in data:
                all_modules_total.append(float(data['平均总处理时间']))
            if '平均FPS' in data:
                all_modules_fps.append(float(data['平均FPS']))
            if '平均CPU使用率' in data:
                all_modules_cpu.append(float(data['平均CPU使用率']))
            if '平均内存使用' in data:
                all_modules_memory.append(float(data['平均内存使用']))
            if '平均GPU使用率' in data:
                all_modules_gpu_util.append(float(data['平均GPU使用率']))
            if '平均GPU显存' in data:
                all_modules_gpu_memory.append(float(data['平均GPU显存']))
    
    if all_modules_total:
        avg_unit_box = sum(all_modules_unit_box) / len(all_modules_unit_box) if all_modules_unit_box else None
        avg_ocr = sum(all_modules_ocr) / len(all_modules_ocr) if all_modules_ocr else None
        avg_total = sum(all_modules_total) / len(all_modules_total)
        avg_fps = sum(all_modules_fps) / len(all_modules_fps)
        avg_cpu = sum(all_modules_cpu) / len(all_modules_cpu)
        avg_memory = sum(all_modules_memory) / len(all_modules_memory)
        
        report_lines.append(f"\n📊 系统整体性能指标:")
        if avg_unit_box is not None:
            report_lines.append(f"  • 全局平均单位框耗时: {avg_unit_box:.2f} ms/框")
        if avg_ocr is not None:
            report_lines.append(f"  • 全局平均OCR处理时间: {avg_ocr:.2f} ms")
        report_lines.append(f"  • 全局平均总处理时间: {avg_total:.2f} ms")
        report_lines.append(f"  • 全局平均FPS: {avg_fps:.2f}")
        report_lines.append(f"  • 全局平均CPU使用率: {avg_cpu:.2f}%")
        report_lines.append(f"  • 全局平均内存使用: {avg_memory:.2f} MB")
        
        if all_modules_gpu_util:
            avg_gpu_util = sum(all_modules_gpu_util) / len(all_modules_gpu_util)
            avg_gpu_memory = sum(all_modules_gpu_memory) / len(all_modules_gpu_memory)
            report_lines.append(f"  • 全局平均GPU使用率: {avg_gpu_util:.2f}%")
            report_lines.append(f"  • 全局平均GPU显存: {avg_gpu_memory:.2f} MB")

        # 追加全局汇总到 CSV 列表
        module_summaries.append(
            {
                "module": "GLOBAL",
                "avg_unit_box_ms": f"{avg_unit_box:.2f}" if avg_unit_box is not None else "",
                "avg_ocr_ms": f"{avg_ocr:.2f}" if avg_ocr is not None else "",
                "avg_total_ms": f"{avg_total:.2f}",
                "avg_fps": f"{avg_fps:.2f}",
                "avg_cpu_percent": f"{avg_cpu:.2f}",
                "avg_mem_mb": f"{avg_memory:.2f}",
                "avg_gpu_util_percent": f"{avg_gpu_util:.2f}" if all_modules_gpu_util else "",
                "avg_gpu_mem_mb": f"{avg_gpu_memory:.2f}" if all_modules_gpu_util else "",
                "avg_success_rate_percent": "",
                "total_runtime_seconds": "",
            }
        )
        
        # 性能评级（优先基于单位框耗时，其次基于平均OCR处理时间）
        report_lines.append(f"\n⭐ 性能评级:")
        
        # 单位框耗时评级 / 平均OCR时间评级（阈值可根据业务调整）
        base_value = None
        base_label = ""
        if avg_unit_box is not None:
            base_value = avg_unit_box
            base_label = "单位框耗时"
        elif avg_ocr is not None:
            base_value = avg_ocr
            base_label = "平均OCR处理时间"

        if base_value is not None:
            if base_value < 10:
                ocr_rating = "优秀 ⭐⭐⭐⭐⭐"
            elif base_value < 20:
                ocr_rating = "良好 ⭐⭐⭐⭐"
            elif base_value < 40:
                ocr_rating = "一般 ⭐⭐⭐"
            else:
                ocr_rating = "需优化 ⭐⭐"
            report_lines.append(f"  • {base_label}: {ocr_rating} ({base_value:.2f} ms{'/框' if base_label == '单位框耗时' else ''})")

        # FPS评级
        if avg_fps >= 10:
            fps_rating = "优秀 ⭐⭐⭐⭐⭐"
        elif avg_fps >= 6:
            fps_rating = "良好 ⭐⭐⭐⭐"
        elif avg_fps >= 3:
            fps_rating = "一般 ⭐⭐⭐"
        else:
            fps_rating = "需优化 ⭐⭐"
        report_lines.append(f"  • 实时性能(FPS): {fps_rating} ({avg_fps:.2f}fps)")
        
        # GPU使用率评级
        if all_modules_gpu_util:
            if 30 <= avg_gpu_util <= 60:
                gpu_rating = "优秀 ⭐⭐⭐⭐⭐ (GPU利用合理)"
            elif avg_gpu_util < 30:
                gpu_rating = "良好 ⭐⭐⭐⭐ (GPU利用偏低)"
            elif avg_gpu_util < 80:
                gpu_rating = "一般 ⭐⭐⭐ (GPU利用偏高)"
            else:
                gpu_rating = "需优化 ⭐⭐ (GPU利用过高)"
            report_lines.append(f"  • GPU资源利用: {gpu_rating} ({avg_gpu_util:.1f}%)")
    
    report_lines.append(f"\n{'═' * 80}")
    report_lines.append("报告生成完成！")
    report_lines.append(f"{'═' * 80}\n")
    
    # 写入报告文件
    report_content = "\n".join(report_lines)
    
    # 报告文件保存到 reports 文件夹
    output_path = os.path.join(reports_folder, output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    # 写入 CSV 汇总
    csv_path = os.path.join(reports_folder, output_csv_file)
    if module_summaries:
        headers = [
            "module",
            "avg_unit_box_ms",
            "avg_ocr_ms",
            "avg_total_ms",
            "avg_fps",
            "avg_cpu_percent",
            "avg_mem_mb",
            "avg_gpu_util_percent",
            "avg_gpu_mem_mb",
            "avg_success_rate_percent",
            "total_runtime_seconds",
        ]
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as cf:
            writer = csv.DictWriter(cf, fieldnames=headers)
            writer.writeheader()
            writer.writerows(module_summaries)

    print(f"\n✅ 性能汇总报告已生成: {output_path}")
    if module_summaries:
        print(f"✅ 性能汇总CSV已生成: {csv_path}")
    
    return output_path


if __name__ == "__main__":
    generate_performance_report()

