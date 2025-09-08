#!/usr/bin/env python3
"""
语法检查脚本
检查Python文件的语法是否正确
"""

import ast
import sys
import os

def check_python_syntax(file_path):
    """检查Python文件语法"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # 尝试解析AST
        ast.parse(source, filename=file_path)
        return True, "语法正确"
        
    except SyntaxError as e:
        return False, f"语法错误: {e.msg} (行 {e.lineno})"
    except Exception as e:
        return False, f"检查失败: {str(e)}"

def main():
    """主函数"""
    print("Python语法检查工具")
    print("=" * 40)
    
    # 要检查的文件列表
    files_to_check = [
        'app.py',
        'web/app.py',
        'main_controller.py',
        'run_web.py',
        'diagnose.py',
        'test_system.py',
        'test_database_selection.py'
    ]
    
    all_ok = True
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            success, message = check_python_syntax(file_path)
            status = "✅" if success else "❌"
            print(f"{status} {file_path}: {message}")
            
            if not success:
                all_ok = False
        else:
            print(f"⚠️  {file_path}: 文件不存在")
    
    print("\n" + "=" * 40)
    if all_ok:
        print("🎉 所有文件语法检查通过！")
        return True
    else:
        print("❌ 发现语法错误，请修复后重试")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)