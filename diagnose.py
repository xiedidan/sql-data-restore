#!/usr/bin/env python3
"""
环境诊断脚本
快速检查和诊断运行环境问题
"""

import sys
import os
import subprocess
import importlib.util

def print_header(title):
    """打印标题"""
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")

def print_status(item, status, details=""):
    """打印状态"""
    status_icon = "✅" if status else "❌"
    print(f"{status_icon} {item}")
    if details:
        print(f"   {details}")

def check_python_version():
    """检查Python版本"""
    print_header("Python环境检查")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print_status("Python版本", True, f"Python {version_str}")
    
    if version < (3, 8):
        print_status("版本要求", False, "需要Python 3.8+")
        return False
    else:
        print_status("版本要求", True, "满足最低要求")
    
    # 检查Python路径
    python_path = sys.executable
    print_status("Python路径", True, python_path)
    
    return True

def check_virtual_environment():
    """检查虚拟环境"""
    print_header("虚拟环境检查")
    
    # 检查是否在虚拟环境中
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if in_venv:
        venv_path = os.environ.get('VIRTUAL_ENV', '未知')
        print_status("虚拟环境状态", True, f"已激活: {venv_path}")
    else:
        print_status("虚拟环境状态", False, "未检测到虚拟环境")
        
        # 检查是否存在venv目录
        if os.path.exists('venv'):
            print_status("venv目录", True, "存在，但未激活")
            print("   💡 建议运行: source venv/bin/activate")
        else:
            print_status("venv目录", False, "不存在")
            print("   💡 建议运行: python3 -m venv venv")
    
    return in_venv

def check_dependencies():
    """检查依赖库"""
    print_header("依赖库检查")
    
    required_packages = [
        ('flask', 'Flask Web框架'),
        ('flask_socketio', 'Flask-SocketIO实时通信'),
        ('yaml', 'PyYAML配置文件解析'),
        ('requests', 'HTTP请求库'),
        ('pymysql', 'MySQL数据库驱动'),
        ('psycopg2', 'PostgreSQL数据库驱动'),
    ]
    
    all_ok = True
    missing_packages = []
    
    for package, description in required_packages:
        try:
            if package == 'yaml':
                import yaml
            elif package == 'psycopg2':
                import psycopg2
            else:
                __import__(package)
            print_status(description, True, f"{package} 已安装")
        except ImportError:
            print_status(description, False, f"{package} 未安装")
            missing_packages.append(package)
            all_ok = False
    
    if missing_packages:
        print(f"\n💡 安装缺失的依赖:")
        print(f"   pip install {' '.join(missing_packages)}")
        print(f"   或运行: pip install -r requirements.txt")
    
    return all_ok

def check_configuration():
    """检查配置文件"""
    print_header("配置文件检查")
    
    config_exists = os.path.exists('config.yaml')
    example_exists = os.path.exists('config.yaml.example')
    
    print_status("config.yaml", config_exists, "主配置文件")
    print_status("config.yaml.example", example_exists, "示例配置文件")
    
    if not config_exists and example_exists:
        print("   💡 建议运行: cp config.yaml.example config.yaml")
    
    # 如果配置文件存在，尝试解析
    if config_exists:
        try:
            import yaml
            with open('config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 检查关键配置项
            database_config = config.get('database', {})
            target_type = database_config.get('target_type', 'doris')
            
            print_status("配置文件格式", True, "YAML格式正确")
            print_status("目标数据库类型", True, target_type)
            
            # 检查对应数据库配置
            if target_type in database_config:
                db_config = database_config[target_type]
                required_fields = ['host', 'port', 'user', 'database']
                missing_fields = [field for field in required_fields if field not in db_config]
                
                if missing_fields:
                    print_status(f"{target_type}数据库配置", False, f"缺少字段: {', '.join(missing_fields)}")
                else:
                    print_status(f"{target_type}数据库配置", True, "配置完整")
            else:
                print_status(f"{target_type}数据库配置", False, "配置缺失")
            
        except Exception as e:
            print_status("配置文件解析", False, f"解析错误: {e}")
            return False
    
    return config_exists

def check_project_structure():
    """检查项目结构"""
    print_header("项目结构检查")
    
    required_files = [
        ('app.py', '主启动文件'),
        ('main_controller.py', '主控制器'),
        ('requirements.txt', '依赖列表'),
        ('core/', '核心模块目录'),
        ('web/', 'Web模块目录'),
        ('templates/', '模板目录'),
        ('static/', '静态资源目录'),
    ]
    
    all_ok = True
    
    for file_path, description in required_files:
        exists = os.path.exists(file_path)
        print_status(description, exists, file_path)
        if not exists:
            all_ok = False
    
    return all_ok

def check_network_ports():
    """检查网络端口"""
    print_header("网络端口检查")
    
    try:
        import socket
        
        # 检查端口5000是否可用
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        
        if result == 0:
            print_status("端口5000", False, "端口被占用")
            print("   💡 建议: 停止占用端口的程序或使用其他端口")
        else:
            print_status("端口5000", True, "端口可用")
            
    except Exception as e:
        print_status("端口检查", False, f"检查失败: {e}")

def provide_solutions():
    """提供解决方案"""
    print_header("快速解决方案")
    
    print("🔧 常见问题解决:")
    print()
    print("1. 虚拟环境问题:")
    print("   source venv/bin/activate")
    print()
    print("2. 依赖安装:")
    print("   pip install -r requirements.txt")
    print()
    print("3. 配置文件:")
    print("   cp config.yaml.example config.yaml")
    print("   # 然后编辑config.yaml")
    print()
    print("4. 启动应用:")
    print("   python run_web.py          # 简化启动")
    print("   python app.py --mode web   # 直接启动")
    print("   ./start-venv.sh            # 脚本启动")
    print()
    print("5. 查看详细指南:")
    print("   cat VIRTUAL_ENV_GUIDE.md")
    print("   cat QUICK_START.md")

def main():
    """主函数"""
    print("Oracle到多数据库迁移工具 - 环境诊断")
    print("诊断时间:", __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # 执行各项检查
    checks = [
        ("Python版本", check_python_version),
        ("虚拟环境", check_virtual_environment),
        ("依赖库", check_dependencies),
        ("配置文件", check_configuration),
        ("项目结构", check_project_structure),
        ("网络端口", check_network_ports),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print_status(f"{name}检查", False, f"检查异常: {e}")
            results[name] = False
    
    # 总结
    print_header("诊断总结")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"检查项目: {total}")
    print(f"通过项目: {passed}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有检查通过！环境配置正常")
        print("💡 可以运行: python run_web.py 启动应用")
    else:
        print(f"\n⚠️  发现 {total-passed} 个问题，请参考上述检查结果修复")
        provide_solutions()

if __name__ == "__main__":
    main()