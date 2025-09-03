#!/usr/bin/env python3
"""
SQL解析器性能基准测试

比较不同解析策略的性能差异
"""

import os
import sys
import time
import tempfile
import threading
from typing import Dict, List

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def create_test_sql_file(file_path: str, num_rows: int = 100000, table_name: str = "test_table"):
    """创建测试SQL文件"""
    print(f"创建测试文件: {file_path} ({num_rows:,} 行)")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        # 写入注释
        f.write(f"-- 测试SQL文件，包含 {num_rows:,} 行数据\n")
        f.write(f"-- 表名: {table_name}\n")
        f.write("-- 生成时间: " + time.strftime('%Y-%m-%d %H:%M:%S') + "\n\n")
        
        # 写入INSERT语句
        for i in range(num_rows):
            if i % 10000 == 0:
                print(f"  写入进度: {i:,}/{num_rows:,} ({i/num_rows*100:.1f}%)")
            
            row_id = i + 1
            name = f"User_{row_id}"
            email = f"user{row_id}@example.com"
            age = 20 + (i % 60)
            salary = 3000 + (i % 50) * 100
            department = f"Dept_{(i % 10) + 1}"
            created_date = f"2023-{(i%12)+1:02d}-{(i%28)+1:02d}"
            
            f.write(f"INSERT INTO {table_name} (id, name, email, age, salary, department, created_date) ")
            f.write(f"VALUES ({row_id}, '{name}', '{email}', {age}, {salary}, '{department}', '{created_date}');\n")
    
    file_size = os.path.getsize(file_path)
    print(f"测试文件创建完成: {file_size / (1024*1024):.2f} MB")
    return file_path

def benchmark_parser(parser_name: str, parser_instance, file_path: str, n_lines: int = 100) -> Dict:
    """基准测试解析器"""
    print(f"\n=== 测试 {parser_name} ===")
    
    results = []
    
    # 执行多次测试
    for i in range(3):
        start_time = time.time()
        
        try:
            if hasattr(parser_instance, 'extract_sample_data_fast'):
                result = parser_instance.extract_sample_data_fast(file_path, n_lines)
            elif hasattr(parser_instance, 'extract_sample_data_threaded'):
                result = parser_instance.extract_sample_data_threaded(file_path, n_lines)
            else:
                result = parser_instance.extract_sample_data(file_path, n_lines)
            
            end_time = time.time()
            parse_time = end_time - start_time
            
            results.append(parse_time)
            
            print(f"  测试 {i+1}: {parse_time:.3f}s")
            print(f"    表名: {result.get('table_name', 'N/A')}")
            print(f"    样本行数: {len(result.get('sample_data', []))}")
            print(f"    估计总行数: {result.get('estimated_rows', 0):,}")
            
        except Exception as e:
            print(f"  测试 {i+1} 失败: {str(e)}")
            results.append(float('inf'))
    
    # 计算统计信息
    valid_results = [r for r in results if r != float('inf')]
    if valid_results:
        avg_time = sum(valid_results) / len(valid_results)
        min_time = min(valid_results)
        max_time = max(valid_results)
        
        print(f"  平均时间: {avg_time:.3f}s")
        print(f"  最佳时间: {min_time:.3f}s")
        print(f"  最差时间: {max_time:.3f}s")
        
        return {
            'parser': parser_name,
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'success_rate': len(valid_results) / len(results)
        }
    else:
        print(f"  所有测试失败")
        return {
            'parser': parser_name,
            'avg_time': float('inf'),
            'min_time': float('inf'),
            'max_time': float('inf'),
            'success_rate': 0
        }

def run_performance_benchmark():
    """运行性能基准测试"""
    print("🚀 SQL解析器性能基准测试")
    print("=" * 60)
    
    # 测试文件大小配置
    test_configs = [
        {'name': '小文件 (1万行)', 'rows': 10000},
        {'name': '中等文件 (10万行)', 'rows': 100000},
        {'name': '大文件 (50万行)', 'rows': 500000},
    ]
    
    all_results = []
    
    for config in test_configs:
        print(f"\n{'='*20} {config['name']} {'='*20}")
        
        # 创建测试文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as temp_file:
            test_file = temp_file.name
        
        try:
            create_test_sql_file(test_file, config['rows'])
            file_size_mb = os.path.getsize(test_file) / (1024 * 1024)
            print(f"文件大小: {file_size_mb:.2f} MB")
            
            # 基础配置
            base_config = {
                'migration': {'sample_lines': 100},
                'parser': {
                    'use_fast_parser': True,
                    'fast_parser_threshold': 0,  # 总是使用快速解析器
                    'chunk_size': 1024 * 1024,
                    'max_workers': 4
                }
            }
            
            test_results = []
            
            # 1. 测试传统解析器
            try:
                from core.sql_parser import SQLFileParser
                traditional_parser = SQLFileParser(base_config)
                traditional_parser.use_fast_parser = False  # 强制使用传统解析
                result = benchmark_parser("传统解析器", traditional_parser, test_file, 100)
                test_results.append(result)
            except Exception as e:
                print(f"传统解析器测试失败: {e}")
            
            # 2. 测试快速解析器
            try:
                from core.fast_sql_parser import FastSQLParser
                fast_parser = FastSQLParser(base_config)
                result = benchmark_parser("快速解析器", fast_parser, test_file, 100)
                test_results.append(result)
            except Exception as e:
                print(f"快速解析器测试失败: {e}")
            
            # 3. 测试多线程解析器（仅大文件）
            if config['rows'] >= 100000:
                try:
                    from core.fast_sql_parser import ThreadedSQLParser
                    threaded_parser = ThreadedSQLParser(base_config)
                    result = benchmark_parser("多线程解析器", threaded_parser, test_file, 100)
                    test_results.append(result)
                except Exception as e:
                    print(f"多线程解析器测试失败: {e}")
            
            # 保存结果
            for result in test_results:
                result['file_config'] = config['name']
                result['file_size_mb'] = file_size_mb
                all_results.append(result)
                
        finally:
            # 清理测试文件
            if os.path.exists(test_file):
                os.unlink(test_file)
    
    # 生成性能报告
    print_performance_report(all_results)

def print_performance_report(results: List[Dict]):
    """打印性能报告"""
    print(f"\n{'='*60}")
    print("📊 性能基准测试报告")
    print(f"{'='*60}")
    
    if not results:
        print("❌ 没有可用的测试结果")
        return
    
    # 按文件配置分组
    configs = {}
    for result in results:
        config_name = result['file_config']
        if config_name not in configs:
            configs[config_name] = []
        configs[config_name].append(result)
    
    for config_name, config_results in configs.items():
        print(f"\n{config_name}")
        print("-" * 40)
        
        # 按平均时间排序
        config_results.sort(key=lambda x: x['avg_time'])
        
        baseline_time = None
        for i, result in enumerate(config_results):
            if result['success_rate'] > 0:
                if baseline_time is None:
                    baseline_time = result['avg_time']
                    speedup = 1.0
                else:
                    speedup = baseline_time / result['avg_time']
                
                print(f"{i+1}. {result['parser']:<15} | "
                      f"平均: {result['avg_time']:.3f}s | "
                      f"最佳: {result['min_time']:.3f}s | "
                      f"成功率: {result['success_rate']*100:.0f}% | "
                      f"加速比: {speedup:.1f}x")
            else:
                print(f"{i+1}. {result['parser']:<15} | 测试失败")
    
    # 总结建议
    print(f"\n💡 性能优化建议:")
    
    # 找出最佳解析器
    successful_results = [r for r in results if r['success_rate'] > 0]
    if successful_results:
        best_result = min(successful_results, key=lambda x: x['avg_time'])
        print(f"✅ 推荐使用: {best_result['parser']}")
        print(f"   平均解析时间: {best_result['avg_time']:.3f}s")
        
        # 计算性能提升
        traditional_results = [r for r in successful_results if '传统' in r['parser']]
        if traditional_results:
            traditional_time = traditional_results[0]['avg_time']
            improvement = ((traditional_time - best_result['avg_time']) / traditional_time) * 100
            print(f"   相比传统解析器提升: {improvement:.1f}%")
    
    # 文件大小建议
    print(f"\n📏 文件大小建议:")
    print(f"• 小文件 (<10MB): 使用快速解析器")
    print(f"• 中等文件 (10-100MB): 使用快速解析器 + 内存映射")
    print(f"• 大文件 (>100MB): 使用多线程解析器")

def test_memory_usage():
    """测试内存使用情况"""
    print(f"\n🧠 内存使用测试")
    print("-" * 40)
    
    try:
        import psutil
        process = psutil.Process()
        
        # 测试前内存
        memory_before = process.memory_info().rss / (1024 * 1024)
        print(f"测试前内存: {memory_before:.1f} MB")
        
        # 创建大文件并解析
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as temp_file:
            test_file = temp_file.name
        
        try:
            create_test_sql_file(test_file, 100000)
            
            from core.fast_sql_parser import FastSQLParser
            parser = FastSQLParser({'migration': {'sample_lines': 100}})
            
            result = parser.extract_sample_data_fast(test_file, 100)
            
            # 测试后内存
            memory_after = process.memory_info().rss / (1024 * 1024)
            memory_used = memory_after - memory_before
            
            print(f"测试后内存: {memory_after:.1f} MB")
            print(f"内存增长: {memory_used:.1f} MB")
            print(f"文件大小: {os.path.getsize(test_file) / (1024*1024):.1f} MB")
            print(f"内存效率: {memory_used / (os.path.getsize(test_file) / (1024*1024)):.2f}")
            
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)
                
    except ImportError:
        print("❌ psutil不可用，跳过内存测试")
        print("   安装方法: pip install psutil")

if __name__ == "__main__":
    try:
        run_performance_benchmark()
        test_memory_usage()
        
        print(f"\n✅ 性能基准测试完成")
        print(f"💡 基于测试结果，建议在配置文件中设置合适的解析器参数")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()