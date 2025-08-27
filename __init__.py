"""
Oracle到Doris数据迁移系统

主要功能:
1. 解析Oracle导出的SQL文件
2. 调用DeepSeek AI推断表结构
3. 生成Doris建表语句
4. 提供Web界面供用户确认修改
5. 并行高效导入数据到Doris

Author: Migration System
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Migration System"

from .core.sql_parser import SQLFileParser
from .core.schema_inference import SchemaInferenceEngine
from .core.doris_connection import DorisConnection
from .core.parallel_importer import ParallelImporter
from .web.app import MigrationWebApp
from .main_controller import OracleDoriseMigrator

__all__ = [
    'SQLFileParser',
    'SchemaInferenceEngine', 
    'DorisConnection',
    'ParallelImporter',
    'MigrationWebApp',
    'OracleDoriseMigrator'
]