#!/usr/bin/env python3
"""
直接启动Web界面的简化脚本
适用于已经激活虚拟环境的情况
"""

import sys
import os
import subprocess

def check_environment():
    """检查运行环境"""
    print("=== 环境检查 ===")
    
    # 检查Python版本
    python_version = sys.version_info
    print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("❌ Python版本过低，需要3.8+")
        return False
    
    # 检查虚拟环境
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ 检测到虚拟环境")
    else:
        print("⚠️  未检测到虚拟环境，建议使用虚拟环境")
    
    # 检查配置文件
    if os.path.exists('config.yaml'):
        print("✅ 配置文件存在")
    elif os.path.exists('config.yaml.example'):
        print("⚠️  配置文件不存在，正在复制示例文件...")
        import shutil
        shutil.copy('config.yaml.example', 'config.yaml')
        print("📝 请编辑 config.yaml 文件配置数据库连接和API密钥")
        return False
    else:
        print("❌ 配置文件不存在")
        return False
    
    # 检查关键模块
    try:
        import flask
        import flask_socketio
        import yaml
        print("✅ 关键依赖库已安装")
    except ImportError as e:
        print(f"❌ 缺少依赖库: {e}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def start_web_app():
    """启动Web应用"""
    print("\n=== 启动Web应用 ===")
    
    try:
        # 导入Web应用
        from web.app import MigrationWebApp
        
        print("🚀 正在启动Web界面...")
        print("📱 请在浏览器中访问: http://localhost:5000")
        print("⏹️  按 Ctrl+C 停止服务")
        print()
        
        # 创建并启动应用
        app = MigrationWebApp("config.yaml")
        app.run()
        
    except KeyboardInterrupt:
        print("\n👋 Web应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("\n🔧 故障排除建议:")
        print("1. 检查配置文件是否正确")
        print("2. 确认数据库连接参数")
        print("3. 查看详细错误日志")
        return False
    
    return True

def main():
    """主函数"""
    print("Oracle到多数据库迁移工具 - Web界面启动器")
    print("=" * 50)
    
    # 环境检查
    if not check_environment():
        print("\n❌ 环境检查失败，请修复后重试")
        sys.exit(1)
    
    # 启动Web应用
    if not start_web_app():
        sys.exit(1)

if __name__ == "__main__":
    main()