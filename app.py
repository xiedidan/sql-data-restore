#!/usr/bin/env python3
"""
Oracle到Doris迁移工具 - 快速启动脚本

提供多种启动方式的便捷入口
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def start_web_interface():
    """启动Web界面"""
    print("启动Web界面...")
    
    try:
        from web.app import MigrationWebApp
        
        app = MigrationWebApp("config.yaml")
        print("\n" + "="*60)
        print("🚀 Oracle到Doris迁移工具 Web界面启动")
        print("="*60)
        print("📱 访问地址: http://localhost:5000")
        print("📖 使用说明:")
        print("   1. 在Web界面上传SQL文件")
        print("   2. 等待AI推断表结构")
        print("   3. 确认或修改DDL语句")
        print("   4. 开始数据导入")
        print("="*60)
        print("💡 按 Ctrl+C 停止服务")
        print()
        
        app.run()
        
    except KeyboardInterrupt:
        print("\n✋ Web服务已停止")
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请先安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

def start_cli_mode():
    """启动命令行模式"""
    print("启动命令行模式...")
    
    try:
        from main_controller import OracleDoriseMigrator
        
        print("\n" + "="*60)
        print("🔧 Oracle到Doris迁移工具 命令行模式")
        print("="*60)
        
        # 交互式选择文件
        while True:
            print("\n📁 请选择SQL文件:")
            sql_file = input("输入SQL文件路径 (或输入 'quit' 退出): ").strip()
            
            if sql_file.lower() == 'quit':
                print("👋 再见!")
                break
            
            if not os.path.exists(sql_file):
                print(f"❌ 文件不存在: {sql_file}")
                continue
            
            # 初始化迁移器
            migrator = OracleDoriseMigrator("config.yaml")
            
            # 启用进度监控
            def progress_callback(message):
                print(f"[进度] {message}")
            
            migrator.enable_monitoring(progress_callback)
            
            # 执行迁移
            success = migrator.migrate_single_table(sql_file)
            
            if success:
                print(f"✅ 迁移成功: {sql_file}")
            else:
                print(f"❌ 迁移失败: {sql_file}")
                
    except KeyboardInterrupt:
        print("\n✋ 命令行模式已退出")
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请先安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

def run_quick_test():
    """运行快速测试"""
    print("运行快速测试...")
    
    try:
        # 检查示例数据
        sample_dir = project_root / "tests" / "sample_data"
        users_file = sample_dir / "users.sql"
        
        if not users_file.exists():
            print(f"❌ 示例文件不存在: {users_file}")
            return
        
        print("\n" + "="*60)
        print("🧪 运行快速测试")
        print("="*60)
        print(f"📄 测试文件: {users_file}")
        
        from main_controller import OracleDoriseMigrator
        
        # 初始化迁移器（自动确认模式）
        migrator = OracleDoriseMigrator("config.yaml", {"enable_user_confirmation": False})
        
        # 启用进度监控
        def progress_callback(message):
            print(f"[进度] {message}")
        
        migrator.enable_monitoring(progress_callback)
        
        # 执行测试
        success = migrator.migrate_single_table(str(users_file), auto_confirm=True)
        
        print("\n" + "="*60)
        if success:
            print("✅ 快速测试成功!")
            print("系统各模块工作正常，可以开始正式使用")
        else:
            print("❌ 快速测试失败!")
            print("请检查配置和环境设置")
        print("="*60)
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请先安装依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def check_environment():
    """检查环境配置"""
    print("\n" + "="*60)
    print("🔍 环境检查")
    print("="*60)
    
    # 检查Python版本
    python_version = sys.version_info
    print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("⚠️  建议使用Python 3.8+")
    else:
        print("✅ Python版本符合要求")
    
    # 检查配置文件
    config_file = project_root / "config.yaml"
    if config_file.exists():
        print("✅ 配置文件存在")
    else:
        print("❌ 配置文件不存在")
        print("请确保 config.yaml 文件存在并正确配置")
    
    # 检查依赖库
    required_packages = [
        'flask', 'flask_socketio', 'pymysql', 'requests', 
        'pyyaml', 'pandas'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (未安装)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  请安装缺失的依赖:")
        print(f"pip install -r requirements.txt")
    else:
        print(f"\n✅ 所有依赖库已安装")
    
    # 检查示例数据
    sample_dir = project_root / "tests" / "sample_data"
    if sample_dir.exists():
        sample_files = list(sample_dir.glob("*.sql"))
        print(f"✅ 示例数据: {len(sample_files)} 个文件")
    else:
        print("❌ 示例数据目录不存在")
    
    print("="*60)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Oracle到Doris迁移工具")
    parser.add_argument("--mode", choices=["web", "cli", "test", "check"], 
                       default="web", help="启动模式")
    
    args = parser.parse_args()
    
    print("🎯 Oracle到Doris数据迁移工具")
    print("版本: 1.0.0")
    
    # 检查环境
    if args.mode == "check":
        check_environment()
        return
    
    # 快速环境检查
    if not os.path.exists("config.yaml"):
        print("\n❌ 配置文件 config.yaml 不存在")
        print("请先创建并配置该文件，参考项目中的示例配置")
        return
    
    # 根据模式启动
    if args.mode == "web":
        start_web_interface()
    elif args.mode == "cli":
        start_cli_mode()
    elif args.mode == "test":
        run_quick_test()

if __name__ == "__main__":
    main()