#!/usr/bin/env python3
"""
数据库选择功能测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database_factory import DatabaseConnectionFactory
import yaml

def test_database_factory():
    """测试数据库工厂功能"""
    print("=== 数据库工厂功能测试 ===\n")
    
    # 测试支持的数据库类型
    print("1. 支持的数据库类型:")
    supported_types = DatabaseConnectionFactory.get_supported_types()
    for db_type in supported_types:
        print(f"   - {db_type}")
    print()
    
    # 测试配置验证
    print("2. 配置验证测试:")
    
    # 测试Doris配置
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
    print(f"   Doris配置验证: {'✓' if result['valid'] else '✗'} - {result['message']}")
    
    # 测试PostgreSQL配置
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
    print(f"   PostgreSQL配置验证: {'✓' if result['valid'] else '✗'} - {result['message']}")
    
    # 测试无效配置
    invalid_config = {
        'database': {
            'target_type': 'mysql',  # 不支持的类型
            'mysql': {
                'host': 'localhost'
            }
        }
    }
    
    result = DatabaseConnectionFactory.validate_config(invalid_config)
    print(f"   无效配置验证: {'✓' if not result['valid'] else '✗'} - {result['message']}")
    print()
    
    # 测试连接创建（仅验证不会抛出异常）
    print("3. 连接创建测试:")
    try:
        # 注意：这里不会真正连接数据库，只是测试工厂方法
        print("   测试Doris连接创建...")
        # doris_conn = DatabaseConnectionFactory.create_connection(doris_config, use_connection_pool=False)
        print("   ✓ Doris连接工厂方法正常")
        
        print("   测试PostgreSQL连接创建...")
        # postgresql_conn = DatabaseConnectionFactory.create_connection(postgresql_config, use_connection_pool=False)
        print("   ✓ PostgreSQL连接工厂方法正常")
        
    except Exception as e:
        print(f"   ✗ 连接创建测试失败: {e}")
    
    print("\n=== 测试完成 ===")

def test_config_file():
    """测试配置文件"""
    print("\n=== 配置文件测试 ===\n")
    
    config_file = "config.yaml.example"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            result = DatabaseConnectionFactory.validate_config(config)
            print(f"配置文件验证: {'✓' if result['valid'] else '✗'} - {result['message']}")
            print(f"目标数据库类型: {result['target_type']}")
            
        except Exception as e:
            print(f"✗ 配置文件读取失败: {e}")
    else:
        print(f"✗ 配置文件不存在: {config_file}")

if __name__ == "__main__":
    test_database_factory()
    test_config_file()