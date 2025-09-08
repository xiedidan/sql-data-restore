"""
数据库连接工厂模块

根据配置选择合适的数据库连接类型（Doris或PostgreSQL）
"""

import logging
from typing import Dict, Union
from .doris_connection import DorisConnection
from .postgresql_connection import PostgreSQLConnection

class DatabaseConnectionFactory:
    """数据库连接工厂类"""
    
    @staticmethod
    def create_connection(config: Dict, use_connection_pool: bool = True) -> Union[DorisConnection, PostgreSQLConnection]:
        """
        根据配置创建数据库连接
        
        Args:
            config: 配置字典
            use_connection_pool: 是否使用连接池
            
        Returns:
            数据库连接对象
            
        Raises:
            ValueError: 不支持的数据库类型
        """
        logger = logging.getLogger(__name__)
        
        # 获取目标数据库类型
        target_type = config.get('database', {}).get('target_type', 'doris').lower()
        
        if target_type == 'doris':
            logger.info("创建Doris数据库连接")
            return DorisConnection(config, use_connection_pool)
        elif target_type == 'postgresql':
            logger.info("创建PostgreSQL数据库连接")
            return PostgreSQLConnection(config, use_connection_pool)
        else:
            raise ValueError(f"不支持的数据库类型: {target_type}。支持的类型: doris, postgresql")
    
    @staticmethod
    def get_supported_types() -> list:
        """
        获取支持的数据库类型列表
        
        Returns:
            支持的数据库类型列表
        """
        return ['doris', 'postgresql']
    
    @staticmethod
    def validate_config(config: Dict) -> Dict:
        """
        验证数据库配置
        
        Args:
            config: 配置字典
            
        Returns:
            验证结果字典 {'valid': bool, 'message': str, 'target_type': str}
        """
        try:
            database_config = config.get('database', {})
            target_type = database_config.get('target_type', 'doris').lower()
            
            # 检查是否为支持的类型
            if target_type not in DatabaseConnectionFactory.get_supported_types():
                return {
                    'valid': False,
                    'message': f"不支持的数据库类型: {target_type}。支持的类型: {', '.join(DatabaseConnectionFactory.get_supported_types())}",
                    'target_type': target_type
                }
            
            # 检查对应的数据库配置是否存在
            if target_type not in database_config:
                return {
                    'valid': False,
                    'message': f"缺少 {target_type} 数据库配置",
                    'target_type': target_type
                }
            
            # 检查必需的配置项
            db_config = database_config[target_type]
            required_fields = ['host', 'port', 'user', 'database']
            
            missing_fields = []
            for field in required_fields:
                if field not in db_config or db_config[field] is None:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    'valid': False,
                    'message': f"{target_type} 数据库配置缺少必需字段: {', '.join(missing_fields)}",
                    'target_type': target_type
                }
            
            return {
                'valid': True,
                'message': f"{target_type} 数据库配置验证通过",
                'target_type': target_type
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f"配置验证异常: {str(e)}",
                'target_type': 'unknown'
            }