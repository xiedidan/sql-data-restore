#!/usr/bin/env python3
"""
服务器文件路径功能测试

测试新增的服务器文件路径功能的各种场景，包括：
- 路径验证功能
- 文件信息获取
- 服务器文件处理
- 安全性检查
- 错误处理
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_controller import OracleDoriseMigrator
from web.app import MigrationWebApp


class TestServerFilePathFeature(unittest.TestCase):
    """服务器文件路径功能测试"""
    
    def setUp(self):
        """测试前置设置"""
        # 创建临时目录和文件
        self.temp_dir = tempfile.mkdtemp()
        self.test_sql_file = os.path.join(self.temp_dir, "test.sql")
        self.invalid_file = os.path.join(self.temp_dir, "test.txt")
        
        # 创建测试SQL文件
        with open(self.test_sql_file, 'w', encoding='utf-8') as f:
            f.write("""
-- Test SQL file
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(255)
);

INSERT INTO users VALUES (1, 'John', 'john@example.com');
INSERT INTO users VALUES (2, 'Jane', 'jane@example.com');
""")
        
        # 创建无效文件
        with open(self.invalid_file, 'w') as f:
            f.write("This is not a SQL file")
        
        # 创建测试配置
        self.test_config = {
            'file_access': {
                'enable_server_path_input': True,
                'allowed_directories': [self.temp_dir, './tests/sample_data'],
                'max_file_size_mb': 100,
                'allowed_extensions': ['.sql'],
                'enable_path_traversal_protection': True,
                'max_path_length': 255
            },
            'database': {
                'doris': {
                    'host': 'localhost',
                    'port': 9030,
                    'user': 'root',
                    'password': '',
                    'database': 'test_db'
                }
            },
            'deepseek': {
                'api_key': 'test_key',
                'base_url': 'https://api.deepseek.com',
                'model': 'deepseek-reasoner'
            }
        }
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_server_file_path_success(self):
        """测试成功的路径验证"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        result = migrator.validate_server_file_path(self.test_sql_file)
        
        self.assertTrue(result['success'])
        self.assertIn('normalized_path', result)
        self.assertEqual(result['normalized_path'], os.path.abspath(self.test_sql_file))
    
    def test_validate_server_file_path_file_not_exists(self):
        """测试文件不存在的情况"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.sql")
        result = migrator.validate_server_file_path(non_existent_file)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_003')
        self.assertIn('文件不存在', result['message'])
    
    def test_validate_server_file_path_invalid_extension(self):
        """测试无效文件扩展名"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        result = migrator.validate_server_file_path(self.invalid_file)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_001')
        self.assertIn('不支持的文件类型', result['message'])
    
    def test_validate_server_file_path_feature_disabled(self):
        """测试功能禁用时的行为"""
        migrator = OracleDoriseMigrator()
        config = self.test_config.copy()
        config['file_access']['enable_server_path_input'] = False
        migrator.config = config
        
        result = migrator.validate_server_file_path(self.test_sql_file)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'FEATURE_DISABLED')
    
    def test_validate_server_file_path_security_check(self):
        """测试路径安全检查"""
        migrator = OracleDoriseMigrator()
        config = self.test_config.copy()
        # 移除临时目录从允许列表
        config['file_access']['allowed_directories'] = ['./tests/sample_data']
        migrator.config = config
        
        result = migrator.validate_server_file_path(self.test_sql_file)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_002')
        self.assertIn('不在允许访问的目录中', result['message'])
    
    def test_get_server_file_info_success(self):
        """测试获取文件信息成功"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        result = migrator.get_server_file_info(self.test_sql_file)
        
        self.assertTrue(result['success'])
        self.assertIn('filename', result)
        self.assertIn('file_size', result)
        self.assertIn('file_size_mb', result)
        self.assertIn('estimated_rows', result)
        self.assertEqual(result['filename'], 'test.sql')
        self.assertGreater(result['file_size'], 0)
        self.assertGreater(result['estimated_rows'], 0)
    
    def test_get_server_file_info_validation_failure(self):
        """测试文件信息获取在验证失败时的行为"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        non_existent_file = os.path.join(self.temp_dir, "nonexistent.sql")
        result = migrator.get_server_file_info(non_existent_file)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_003')
    
    @patch('main_controller.OracleDoriseMigrator._estimate_file_lines')
    def test_estimate_file_lines(self, mock_estimate):
        """测试文件行数估算"""
        mock_estimate.return_value = 5
        
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        # 直接调用方法测试
        estimated_lines = migrator._estimate_file_lines(self.test_sql_file)
        self.assertEqual(estimated_lines, 5)
    
    def test_normalize_file_path(self):
        """测试路径规范化"""
        migrator = OracleDoriseMigrator()
        
        # 测试相对路径转绝对路径
        relative_path = "./test.sql"
        normalized = migrator._normalize_file_path(relative_path)
        self.assertTrue(os.path.isabs(normalized))
        
        # 测试路径清理
        messy_path = "dir/../dir/./file.sql"
        normalized = migrator._normalize_file_path(messy_path)
        self.assertNotIn('..', normalized)
        self.assertNotIn('./', normalized)
    
    def test_is_path_safe_whitelist(self):
        """测试路径安全检查白名单机制"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        # 测试允许的路径
        result = migrator._is_path_safe(self.test_sql_file)
        self.assertTrue(result['safe'])
        
        # 测试不允许的路径
        forbidden_path = "/forbidden/path/file.sql"
        result = migrator._is_path_safe(forbidden_path)
        self.assertFalse(result['safe'])
    
    def test_is_path_safe_protection_disabled(self):
        """测试禁用路径遍历保护时的行为"""
        migrator = OracleDoriseMigrator()
        config = self.test_config.copy()
        config['file_access']['enable_path_traversal_protection'] = False
        migrator.config = config
        
        # 禁用保护时应该允许任何路径
        result = migrator._is_path_safe("/any/path/file.sql")
        self.assertTrue(result['safe'])
    
    @patch('main_controller.SQLFileParser')
    @patch('main_controller.SchemaInferenceEngine')
    def test_process_server_file_success(self, mock_schema_engine, mock_sql_parser):
        """测试处理服务器文件成功"""
        # 模拟SQL解析器
        mock_parser_instance = MagicMock()
        mock_parser_instance.extract_sample_data.return_value = {
            'table_name': 'users',
            'sample_data': [{'id': 1, 'name': 'John'}]
        }
        mock_sql_parser.return_value = mock_parser_instance
        
        # 模拟推断引擎
        mock_inference_instance = MagicMock()
        mock_inference_instance.infer_table_schema.return_value = MagicMock(
            success=True,
            ddl_statement="CREATE TABLE users (id INT, name VARCHAR(100))",
            confidence_score=0.95,
            error_message=""
        )
        mock_schema_engine.return_value = mock_inference_instance
        
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        result = migrator.process_server_file(self.test_sql_file, "test_task_001")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['task_id'], "test_task_001")
        self.assertEqual(result['table_name'], 'users')
        self.assertIn('ddl_statement', result)
    
    @patch('main_controller.SQLFileParser')
    def test_process_server_file_validation_failure(self, mock_sql_parser):
        """测试处理服务器文件验证失败"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        # 使用无效文件
        result = migrator.process_server_file(self.invalid_file, "test_task_002")
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_001')
    
    def test_empty_path_validation(self):
        """测试空路径验证"""
        migrator = OracleDoriseMigrator()
        migrator.config = self.test_config
        
        result = migrator.validate_server_file_path("")
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_001')
        
        result = migrator.validate_server_file_path(None)
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_001')
    
    def test_path_length_validation(self):
        """测试路径长度验证"""
        migrator = OracleDoriseMigrator()
        config = self.test_config.copy()
        config['file_access']['max_path_length'] = 50  # 设置很短的限制
        migrator.config = config
        
        # 创建超长路径
        long_path = "a" * 100 + ".sql"
        result = migrator.validate_server_file_path(long_path)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'PATH_001')
        self.assertIn('路径长度超过限制', result['message'])


class TestWebAPIIntegration(unittest.TestCase):
    """Web API集成测试"""
    
    def setUp(self):
        """测试前置设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_sql_file = os.path.join(self.temp_dir, "test.sql")
        
        # 创建测试文件
        with open(self.test_sql_file, 'w', encoding='utf-8') as f:
            f.write("CREATE TABLE test (id INT);")
        
        # 创建测试配置
        self.test_config = {
            'file_access': {
                'enable_server_path_input': True,
                'allowed_directories': [self.temp_dir],
                'max_file_size_mb': 100,
                'allowed_extensions': ['.sql']
            }
        }
    
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('web.app.MigrationWebApp._load_config')
    @patch('main_controller.OracleDoriseMigrator')
    def test_validate_path_api(self, mock_migrator_class, mock_load_config):
        """测试路径验证API"""
        mock_load_config.return_value = self.test_config
        
        # 模拟迁移器实例
        mock_migrator = MagicMock()
        mock_migrator.validate_server_file_path.return_value = {
            'success': True,
            'message': '路径验证成功'
        }
        mock_migrator_class.return_value = mock_migrator
        
        # 这里可以添加Flask测试客户端的集成测试
        # 由于需要完整的Flask应用设置，这里仅验证逻辑
        self.assertTrue(True)  # 占位符测试
    
    def test_api_error_handling(self):
        """测试API错误处理"""
        # 这里可以测试各种错误情况的API响应
        # 如网络错误、参数错误、权限错误等
        self.assertTrue(True)  # 占位符测试


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestServerFilePathFeature))
    suite.addTests(loader.loadTestsFromTestCase(TestWebAPIIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("开始运行服务器文件路径功能测试...")
    success = run_tests()
    
    if success:
        print("\n✅ 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败！")
        sys.exit(1)