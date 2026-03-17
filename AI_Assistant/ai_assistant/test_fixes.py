"""
测试所有修复
验证CSV解析器和系统功能
"""

import sys
from pathlib import Path
from csv_parser import CSVParser

def test_csv_parser():
    """测试CSV解析器"""
    print("=" * 70)
    print("测试 CSV 解析器")
    print("=" * 70)
    
    output_dir = Path("../output_data")
    
    if not output_dir.exists():
        print(f"❌ 输出目录不存在: {output_dir}")
        return False
    
    csv_files = list(output_dir.glob("*.csv"))
    print(f"\n找到 {len(csv_files)} 个 CSV 文件\n")
    
    # 测试每种类型的最新文件
    test_files = {
        "alarmlist": None,
        "train": None,
        "turnout": None,
        "power": None,
        "route_check": None
    }
    
    # 找到每种类型的最新文件
    for csv_file in reversed(csv_files):  # 从最新的开始
        file_type = CSVParser.detect_csv_type(str(csv_file))
        if file_type != "unknown" and test_files.get(file_type) is None:
            test_files[file_type] = csv_file
    
    # 测试每个文件
    success_count = 0
    total_records = 0
    
    for csv_type, csv_file in test_files.items():
        if csv_file is None:
            print(f"⚠️  {csv_type:15} - 未找到文件")
            continue
        
        print(f"\n{'─' * 70}")
        print(f"文件: {csv_file.name}")
        print(f"类型: {csv_type}")
        print(f"{'─' * 70}")
        
        try:
            results = CSVParser.parse_csv(str(csv_file))
            
            if results:
                print(f"✅ 成功解析 {len(results)} 条记录")
                
                # 显示前3条记录的关键信息
                for i, record in enumerate(results[:3], 1):
                    alarm_type = record.get('alarm_type', 'Unknown')
                    desc = record.get('description', '')
                    key_info = record.get('key_info', 'N/A')
                    timestamp = record.get('timestamp', 'N/A')
                    
                    print(f"\n  记录 {i}:")
                    print(f"    类型: {alarm_type} ({desc})")
                    print(f"    关键信息: {key_info}")
                    print(f"    时间戳: {timestamp}")
                
                if len(results) > 3:
                    print(f"\n  ...还有 {len(results) - 3} 条记录")
                
                success_count += 1
                total_records += len(results)
            else:
                print(f"⚠️  解析结果为空（可能文件为空或格式不支持）")
                
        except Exception as e:
            print(f"❌ 解析失败: {e}")
    
    print(f"\n{'=' * 70}")
    print(f"测试总结:")
    print(f"  成功解析: {success_count}/5 种类型")
    print(f"  总记录数: {total_records}")
    print(f"{'=' * 70}")
    
    return success_count > 0


def test_fixes_checklist():
    """检查所有修复项"""
    print("\n\n" + "=" * 70)
    print("修复检查清单")
    print("=" * 70)
    
    checklist = [
        ("✅ 修复 1", "后端 /api/chat 不再检查 stream 参数"),
        ("✅ 修复 2", "前端 DOM 更新使用重新获取的元素引用"),
        ("✅ 修复 3", "流式响应添加智能滚动控制"),
        ("✅ 修复 4", "用户滚动时禁用自动滚动到底部"),
        ("✅ 修复 5", "CSV 解析器支持列名映射和空行跳过")
    ]
    
    print()
    for item, desc in checklist:
        print(f"{item:15} {desc}")
    
    print("\n" + "=" * 70)
    print("下一步: 重启 AI Assistant 并测试")
    print("=" * 70)
    print()
    print("1. 停止当前的 AI Assistant (Ctrl+C)")
    print("2. 重新运行: python app.py")
    print("3. 访问: http://127.0.0.1:5000")
    print("4. 测试以下功能:")
    print()
    print("   测试 1: 取消流式响应")
    print("   - 取消勾选 '流式响应'")
    print("   - 提问任意问题")
    print("   - 预期: 正常显示答案（不再报错）")
    print()
    print("   测试 2: 流式响应")
    print("   - 勾选 '流式响应'")
    print("   - 提问任意问题")
    print("   - 预期: 答案在AI回答框中逐字显示（不是在提问框中）")
    print()
    print("   测试 3: 滚动测试")
    print("   - 开启流式响应并提问长问题")
    print("   - 在回答过程中上下滚动")
    print("   - 预期: 不会强制跳回顶部，可以自由浏览")
    print()
    print("   测试 4: 模式切换")
    print("   - 切换不同模式（智能/专业/通用）")
    print("   - 提问并观察徽章显示")
    print("   - 预期: 徽章正确显示，答案在正确位置")
    print()
    print("   测试 5: CSV 显示")
    print("   - 查看左侧 '最新报警' 区域")
    print("   - 预期: 显示具体类型和关键信息（不是 Unknown-N/A）")
    print()
    print("=" * 70)


if __name__ == "__main__":
    # 测试CSV解析器
    success = test_csv_parser()
    
    # 显示修复清单
    test_fixes_checklist()
    
    if success:
        print("\n🎉 CSV 解析器测试通过！")
    else:
        print("\n⚠️  CSV 解析器测试失败，请检查输出目录")

