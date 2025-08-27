"""
核心模块
包含SQL解析、AI推断、数据库连接、并行导入等核心功能
"""

from .sql_parser import SQLFileParser, TableSchema
from .schema_inference import SchemaInferenceEngine
from .doris_connection import DorisConnection
from .parallel_importer import ParallelImporter

__all__ = [
    'SQLFileParser',
    'TableSchema',
    'SchemaInferenceEngine',
    'DorisConnection', 
    'ParallelImporter'
]