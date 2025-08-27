#!/usr/bin/env python3
"""
Oracle到Doris迁移工具 - 命令行测试脚本

用于测试系统的各个功能模块
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from main_controller import OracleDoriseMigrator

def setup_test_logging():
    """设置测试日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('test_migration.log', encoding='utf-8')
        ]
    )

def test_single_table(sql_file: str, auto_confirm: bool = False):
    """测试单表迁移"""
    print(f"\n{'='*60}")
    print(f"测试单表迁移: {sql_file}")
    print(f"{'='*60}")
    
    try:
        # 初始化迁移器
        migrator = OracleDoriseMigrator("config.yaml")
        
        # 启用监控回调
        def progress_callback(message):
            print(f"[进度] {message}")
        
        def error_callback(error):
            print(f"[错误] {error}")
        
        def completion_callback(result):
            print(f"[完成] 导入行数: {result.total_rows_imported}, "
                  f"耗时: {result.total_execution_time:.2f}秒")
        
        migrator.enable_monitoring(progress_callback, error_callback, completion_callback)
        
        # 执行迁移
        success = migrator.migrate_single_table(sql_file, auto_confirm)
        
        if success:
            print(f"✅ 表迁移成功: {sql_file}")
        else:
            print(f"❌ 表迁移失败: {sql_file}")
        
        return success
        
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        return False

def test_multiple_tables(sql_files: list, auto_confirm: bool = False):
    """测试多表迁移"""
    print(f"\n{'='*60}")
    print(f"测试多表迁移: {len(sql_files)} 个表")
    print(f"{'='*60}")
    
    try:
        # 初始化迁移器
        migrator = OracleDoriseMigrator("config.yaml")
        
        # 启用监控回调
        def progress_callback(message):
            print(f"[进度] {message}")
        
        migrator.enable_monitoring(progress_callback)
        
        # 执行批量迁移
        results = migrator.migrate_multiple_tables(sql_files, auto_confirm)
        
        # 打印结果
        print(f"\n批量迁移结果:")
        success_count = 0
        for sql_file, success in results.items():
            status = "✅ 成功" if success else "❌ 失败"
            print(f"  {status}: {sql_file}")
            if success:
                success_count += 1
        
        print(f"\n总计: {success_count}/{len(sql_files)} 个表迁移成功")
        
        return results
        
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        return {}

def test_inference_only(sql_file: str):
    """仅测试推断功能"""
    print(f"\n{'='*60}")
    print(f"测试AI推断: {sql_file}")
    print(f"{'='*60}")
    
    try:
        # 初始化迁移器
        migrator = OracleDoriseMigrator("config.yaml")
        
        # 推断表结构
        schema = migrator.infer_schema(sql_file)
        
        if schema and schema.ddl_statement:
            print(f"✅ 推断成功")
            print(f"表名: {schema.table_name}")
            print(f"估计行数: {schema.estimated_rows}")
            print(f"DDL语句:")
            print("-" * 50)
            print(schema.ddl_statement)
            print("-" * 50)
            return True
        else:
            print(f"❌ 推断失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {str(e)}")
        return False

def run_web_mode():
    """运行Web模式"""
    print(f"\n{'='*60}")
    print("启动Web界面模式")
    print(f"{'='*60}")
    
    try:
        from web.app import MigrationWebApp
        
        app = MigrationWebApp("config.yaml")
        print("Web服务启动中...")
        print("请在浏览器中访问: http://localhost:5000")
        print("按 Ctrl+C 退出")
        
        app.run()
        
    except KeyboardInterrupt:
        print("\nWeb服务已停止")
    except Exception as e:
        print(f"❌ Web服务启动失败: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Oracle到Doris迁移工具测试脚本")
    parser.add_argument("--mode", choices=["single", "multiple", "inference", "web"], 
                       default="single", help="测试模式")
    parser.add_argument("--file", help="SQL文件路径")
    parser.add_argument("--files", nargs="+", help="多个SQL文件路径")
    parser.add_argument("--auto-confirm", action="store_true", 
                       help="自动确认DDL语句，跳过用户交互")
    parser.add_argument("--sample-data", action="store_true",
                       help="使用示例数据进行测试")
    
    args = parser.parse_args()
    
    # 设置日志
    setup_test_logging()
    
    # 检查配置文件
    if not os.path.exists("config.yaml"):
        print("❌ 配置文件 config.yaml 不存在")
        print("请先复制并修改配置文件")
        return
    
    if args.mode == "web":
        run_web_mode()
        return
    
    # 准备测试文件
    if args.sample_data:
        sample_dir = project_root / "tests" / "sample_data"
        test_files = [
            str(sample_dir / "users.sql"),
            str(sample_dir / "products.sql")
        ]
    elif args.files:
        test_files = args.files
    elif args.file:
        test_files = [args.file]
    else:
        # 默认使用示例数据
        sample_dir = project_root / "tests" / "sample_data"
        test_files = [str(sample_dir / "users.sql")]
    
    # 检查文件是否存在
    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return
    
    # 执行测试
    if args.mode == "single":
        test_single_table(test_files[0], args.auto_confirm)
    elif args.mode == "multiple":
        test_multiple_tables(test_files, args.auto_confirm)
    elif args.mode == "inference":
        test_inference_only(test_files[0])

if __name__ == "__main__":
    main()