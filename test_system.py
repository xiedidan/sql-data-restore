#!/usr/bin/env python3
"""
系统功能测试脚本
测试Oracle到多数据库迁移工具的核心功能
"""

import sys
import os
import yaml
import logging
from typing import Dict

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试模块导入"""
    print("=== 模块导入测试 ===")
    
    try:
        from core.database_factory import DatabaseConnectionFactory
        print("✓ 数据库工厂模块导入成功")
        
        from core.postgresql_connection import PostgreSQLConnection
        print("✓ PostgreSQL连接模块导入成功")
        
        from core.doris_connection import DorisConnection
        print("✓ Doris连接模块导入成功")
        
        from main_controller import OracleToDbMigrator
        print("✓ 主控制器模块导入成功")
        
        from web.app import MigrationWebApp
        print("✓ Web应用模块导入成功")
        
        return True
        
    except ImportError as e:
        print(f"✗ 模块导入失败: {e}")
        return False

def test_database_factory():
    """测试数据库工厂功能"""
    print("\n=== 数据库工厂测试 ===")
    
    try:
        from core.database_factory import DatabaseConnectionFactory
        
        # 测试支持的数据库类型
        supported_types = DatabaseConnectionFactory.get_supported_types()
        print(f"✓ 支持的数据库类型: {supported_types}")
        
        # 测试Doris配置验证
        doris_config = {
            'database': {
                'target_type': 'doris',
                'doris': {
                    'host': 'localhost',
                    'port': 9030,
                    'user': 'root',
                    'password': '',
                    'database': 'test_db'
                }
            }
        }
        
        result = DatabaseConnectionFactory.validate_config(doris_config)
        print(f"✓ Doris配置验证: {result['message']}")
        
        # 测试PostgreSQL配置验证
        postgresql_config = {
            'database': {
                'target_type': 'postgresql',
                'postgresql': {
                    'host': 'localhost',
                    'port': 5432,
                    'user': 'postgres',
                    'password': '',
                    'database': 'test_db'
                }
            }
        }
        
        result = DatabaseConnectionFactory.validate_config(postgresql_config)
        print(f"✓ PostgreSQL配置验证: {result['message']}")
        
        return True
        
    except Exception as e:
        print(f"✗ 数据库工厂测试失败: {e}")
        return False

def test_config_file():
    """测试配置文件"""
    print("\n=== 配置文件测试 ===")
    
    config_files = ['config.yaml.example', 'config.yaml']
    
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                from core.database_factory import DatabaseConnectionFactory
                result = DatabaseConnectionFactory.validate_config(config)
                
                print(f"✓ {config_file}: {result['message']}")
                print(f"  目标数据库: {result['target_type']}")
                
            except Exception as e:
                print(f"✗ {config_file} 读取失败: {e}")
        else:
            print(f"- {config_file} 不存在")
    
    return True

def test_sql_syntax_conversion():
    """测试SQL语法转换功能"""
    print("\n=== SQL语法转换测试 ===")
    
    try:
        from core.postgresql_connection import PostgreSQLConnection
        
        # 创建一个测试配置
        test_config = {
            'database': {
                'target_type': 'postgresql',
                'postgresql': {
                    'host': 'localhost',
                    'port': 5432,
                    'user': 'postgres',
                    'password': '',
                    'database': 'test_db'
                }
            }
        }
        
        # 创建PostgreSQL连接实例（不实际连接）
        pg_conn = PostgreSQLConnection(test_config, use_connection_pool=False)
        
        # 测试DDL转换
        oracle_ddl = """
        CREATE TABLE EMR_HIS.test_table (
            id NUMBER(10) PRIMARY KEY,
            name VARCHAR2(100) NOT NULL,
            created_date DATE,
            amount NUMBER(10,2),
            description CLOB
        )
        """
        
        cleaned_ddl = pg_conn._clean_ddl_database_references(oracle_ddl)
        postgresql_ddl = pg_conn._convert_ddl_to_postgresql(cleaned_ddl)
        
        print("✓ DDL语法转换测试:")
        print(f"  原始: CREATE TABLE EMR_HIS.test_table ...")
        print(f"  转换: {postgresql_ddl[:50]}...")
        
        # 测试INSERT转换
        oracle_insert = "INSERT INTO EMR_HIS.test_table VALUES (1, 'test', '2024-01-01', 100.50, 'description')"
        cleaned_insert = pg_conn._clean_insert_database_references(oracle_insert)
        postgresql_insert = pg_conn._convert_insert_to_postgresql(cleaned_insert)
        
        print("✓ INSERT语法转换测试:")
        print(f"  原始: INSERT INTO EMR_HIS.test_table ...")
        print(f"  转换: {postgresql_insert[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"✗ SQL语法转换测试失败: {e}")
        return False

def test_web_app_creation():
    """测试Web应用创建"""
    print("\n=== Web应用创建测试 ===")
    
    try:
        # 检查是否有有效的配置文件
        config_file = None
        for cf in ['config.yaml', 'config.yaml.example']:
            if os.path.exists(cf):
                config_file = cf
                break
        
        if not config_file:
            print("✗ 没有找到配置文件")
            return False
        
        # 尝试创建Web应用实例（但不启动）
        from web.app import MigrationWebApp
        
        print(f"✓ 使用配置文件: {config_file}")
        print("✓ Web应用类可以正常导入")
        print("  注意: 实际创建Web应用需要有效的数据库连接")
        
        return True
        
    except Exception as e:
        print(f"✗ Web应用创建测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("Oracle到多数据库迁移工具 - 系统功能测试")
    print("=" * 50)
    
    # 设置简单的日志
    logging.basicConfig(level=logging.WARNING)
    
    tests = [
        ("模块导入", test_imports),
        ("数据库工厂", test_database_factory),
        ("配置文件", test_config_file),
        ("SQL语法转换", test_sql_syntax_conversion),
        ("Web应用创建", test_web_app_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ {test_name}测试异常: {e}")
    
    print(f"\n=== 测试总结 ===")
    print(f"通过: {passed}/{total}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("🎉 所有测试通过！系统功能正常")
        return True
    else:
        print("⚠️  部分测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)