"""
SQL文件解析模块

负责解析Oracle导出的SQL文件，提取样本数据用于AI推断表结构
"""

import os
import re
import logging
import chardet
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class TableSchema:
    """表结构数据类"""
    table_name: str
    ddl_statement: str
    sample_data: List[str]
    column_count: int
    estimated_rows: int

class SQLFileParser:
    """SQL文件解析器"""
    
    def __init__(self, config: Dict):
        """
        初始化SQL文件解析器
        
        Args:
            config: 配置字典，包含sample_lines等参数
        """
        self.config = config
        self.sample_lines = config.get('migration', {}).get('sample_lines', 100)
        self.use_fast_parser = config.get('parser', {}).get('use_fast_parser', True)
        self.fast_parser_threshold = config.get('parser', {}).get('fast_parser_threshold', 50 * 1024 * 1024)  # 50MB
        self.logger = logging.getLogger(__name__)
        
        # 用于切换到高性能解析器
        self._fast_parser = None
        self._threaded_parser = None
        
    def extract_sample_data(self, file_path: str, n_lines: Optional[int] = None, progress_callback: Optional[callable] = None) -> Dict:
        """
        提取SQL文件的样本数据（智能选择解析策略，支持中文编码检测）
        
        Args:
            file_path: SQL文件路径
            n_lines: 要提取的行数，默认使用配置中的值
            progress_callback: 进度回调函数
            
        Returns:
            包含表名、样本数据等信息的字典
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"SQL文件不存在: {file_path}")
        
        file_size = os.path.getsize(file_path)
        
        # 首先进行编码检测
        if progress_callback:
            progress_callback({
                'stage': 'encoding_detection',
                'message': '正在检测文件编码...',
                'progress': 0
            })
        
        encoding_info = self._detect_file_encoding(file_path)
        detected_encoding = encoding_info['encoding']
        confidence = encoding_info['confidence']
        
        self.logger.info(f"检测到文件编码: {detected_encoding} (置信度: {confidence:.2f})")
        
        # 根据编码检测结果选择解析策略
        if confidence < 0.7:  # 低置信度时使用回退编码策略
            self.logger.warning(f"编码检测置信度较低({confidence:.2f})，使用多编码回退策略")
            return self._extract_with_fallback_encoding(file_path, progress_callback)
        
        # 智能选择解析策略
        if self.use_fast_parser and file_size >= self.fast_parser_threshold:
            return self._extract_with_fast_parser_encoding(file_path, n_lines, progress_callback, detected_encoding)
        else:
            return self._extract_sample_data_with_encoding(file_path, detected_encoding, progress_callback)
    
    def _extract_with_fast_parser_encoding(self, file_path: str, n_lines: Optional[int], progress_callback: Optional[callable], encoding: str) -> Dict:
        """使用高性能解析器（支持指定编码）"""
        try:
            # 懒加载高性能解析器
            if self._fast_parser is None:
                from .fast_sql_parser import FastSQLParser, ThreadedSQLParser
                
                file_size = os.path.getsize(file_path)
                if file_size > 200 * 1024 * 1024:  # 大于200MB使用多线程
                    self._threaded_parser = ThreadedSQLParser(self.config)
                    parser = self._threaded_parser
                    method = parser.extract_sample_data_threaded
                else:
                    self._fast_parser = FastSQLParser(self.config)
                    parser = self._fast_parser
                    method = parser.extract_sample_data_fast
                
                self.logger.info(f"切换到高性能解析器: {parser.__class__.__name__} (编码: {encoding})")
                return method(file_path, n_lines, progress_callback, encoding)
            else:
                return self._fast_parser.extract_sample_data_fast(file_path, n_lines, progress_callback, encoding)
                
        except ImportError:
            self.logger.warning("高性能解析器不可用，回退到编码感知解析")
            return self._extract_sample_data_with_encoding(file_path, encoding, progress_callback)
        except Exception as e:
            self.logger.warning(f"高性能解析失败: {str(e)}，回退到编码感知解析")
            return self._extract_sample_data_with_encoding(file_path, encoding, progress_callback)
    
    def _extract_sample_data_legacy_with_encoding(self, file_path: str, encoding: str, n_lines: Optional[int] = None, progress_callback: Optional[callable] = None) -> Dict:
        """
        使用传统方法和指定编码提取SQL文件的样本数据
        
        Args:
            file_path: SQL文件路径
            encoding: 文件编码
            n_lines: 要提取的行数，默认使用配置中的值
            progress_callback: 进度回调函数
            
        Returns:
            包含表名、样本数据等信息的字典
        """
        if n_lines is None:
            n_lines = self.sample_lines
            
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"SQL文件不存在: {file_path}")
            
        try:
            sample_data = []
            table_name = None
            total_lines = 0
            file_size = os.path.getsize(file_path)
            
            # 发送解析开始事件
            if progress_callback:
                progress_callback({
                    'stage': 'parsing',
                    'message': f'开始解析SQL文件: {os.path.basename(file_path)} ({round(file_size / (1024 * 1024), 2)} MB) [编码: {encoding}]',
                    'progress': 0,
                    'file_size_mb': round(file_size / (1024 * 1024), 2),
                    'encoding': encoding
                })
            
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                for i, line in enumerate(f):
                    total_lines += 1
                    
                    # 提取样本行
                    if i < n_lines:
                        # 清理和标准化行内容
                        cleaned_line = self._clean_and_normalize_line(line.strip())
                        sample_data.append(cleaned_line)
                        
                        # 尝试识别表名
                        if table_name is None:
                            extracted_table = self._extract_table_name_from_line(cleaned_line)
                            if extracted_table:
                                table_name = extracted_table
                                if progress_callback:
                                    progress_callback({
                                        'stage': 'parsing',
                                        'message': f'检测到表名: {table_name}',
                                        'progress': min(50, (i / n_lines) * 50),
                                        'table_name': table_name,
                                        'encoding': encoding
                                    })
                    
                    # 只统计总行数，不全部读取，但发送进度更新
                    if i >= n_lines and i % 50000 == 0:
                        if progress_callback:
                            progress_callback({
                                'stage': 'parsing',
                                'message': f'正在扫描文件，已处理 {i:,} 行',
                                'progress': min(90, 50 + (i / max(file_size / 100, 1)) * 40),
                                'encoding': encoding
                            })
                        continue
                        
            # 如果没有从INSERT语句中提取到表名，尝试从文件名推断
            if table_name is None:
                table_name = self._extract_table_name_from_filename(file_path)
                
            # 估算文件大小和行数
            estimated_rows = self._estimate_total_rows(file_path, sample_data)
            
            # 发送解析完成事件
            if progress_callback:
                progress_callback({
                    'stage': 'parsing_completed',
                    'message': f'解析完成: {table_name or "unknown_table"}, 估计 {estimated_rows:,} 行 [编码: {encoding}]',
                    'progress': 100,
                    'table_name': table_name,
                    'estimated_rows': estimated_rows,
                    'sample_lines': len(sample_data),
                    'encoding': encoding
                })
            
            self.logger.info(f"成功解析SQL文件: {file_path}, 表名: {table_name}, 样本行数: {len(sample_data)}, 编码: {encoding}")
            
            return {
                'file_path': file_path,
                'table_name': table_name,
                'sample_data': sample_data,
                'file_size': file_size,
                'estimated_rows': estimated_rows,
                'total_lines': total_lines,
                'encoding': encoding
            }
            
        except Exception as e:
            self.logger.error(f"解析SQL文件失败: {file_path}, 编码: {encoding}, 错误: {str(e)}")
            if progress_callback:
                progress_callback({
                    'stage': 'parsing_failed',
                    'message': f'解析失败: {str(e)}',
                    'progress': 0,
                    'error': str(e),
                    'encoding': encoding
                })
            raise
    
    def identify_table_name(self, sql_content: str) -> str:
        """
        从SQL内容中识别表名
        
        Args:
            sql_content: SQL内容字符串
            
        Returns:
            表名字符串
        """
        # 尝试多种模式匹配INSERT语句中的表名
        patterns = [
            r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s*\(',
            r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s+VALUES',
            r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s+\(',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sql_content, re.IGNORECASE)
            if match:
                return match.group(2)
                
        return None
    
    def extract_insert_statements(self, file_path: str, limit: int = 10) -> List[str]:
        """
        提取INSERT语句样本
        
        Args:
            file_path: SQL文件路径
            limit: 最大提取数量
            
        Returns:
            INSERT语句列表
        """
        insert_statements = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                current_statement = ""
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # 检查是否是INSERT语句开始
                    if line.upper().startswith('INSERT'):
                        if current_statement:
                            # 保存之前的语句
                            insert_statements.append(current_statement)
                            if len(insert_statements) >= limit:
                                break
                        current_statement = line
                    else:
                        # 继续拼接当前语句
                        current_statement += " " + line
                        
                    # 检查语句是否结束（以分号结尾）
                    if current_statement.endswith(';'):
                        insert_statements.append(current_statement)
                        if len(insert_statements) >= limit:
                            break
                        current_statement = ""
                        
                # 添加最后一个语句（如果存在）
                if current_statement and len(insert_statements) < limit:
                    insert_statements.append(current_statement)
                    
        except Exception as e:
            self.logger.error(f"提取INSERT语句失败: {file_path}, 错误: {str(e)}")
            
        return insert_statements
    
    def validate_sql_format(self, sql_content: str) -> bool:
        """
        验证SQL格式是否正确
        
        Args:
            sql_content: SQL内容
            
        Returns:
            是否为有效格式
        """
        if not sql_content:
            return False
            
        # 检查是否包含INSERT语句
        if not re.search(r'INSERT\s+INTO', sql_content, re.IGNORECASE):
            return False
            
        # 检查基本语法结构
        if not re.search(r'VALUES\s*\(', sql_content, re.IGNORECASE):
            return False
            
        return True
    
    def get_column_info_from_sample(self, sample_data: List[str]) -> Dict:
        """
        从样本数据中推断列信息
        
        Args:
            sample_data: 样本数据行列表
            
        Returns:
            包含列信息的字典
        """
        column_info = {
            'column_count': 0,
            'sample_values': [],
            'value_patterns': []
        }
        
        # 查找第一个有效的INSERT语句
        for line in sample_data:
            if line.upper().strip().startswith('INSERT'):
                # 提取VALUES部分
                values_match = re.search(r'VALUES\s*\((.*?)\)', line, re.IGNORECASE | re.DOTALL)
                if values_match:
                    values_str = values_match.group(1)
                    # 简单解析值（这里做基础处理，复杂情况由AI处理）
                    values = self._parse_values_string(values_str)
                    column_info['column_count'] = len(values)
                    column_info['sample_values'].append(values)
                    
                    if len(column_info['sample_values']) >= 5:  # 收集足够样本
                        break
                        
        return column_info
    
    def _extract_table_name_from_line(self, line: str) -> Optional[str]:
        """从单行SQL中提取表名"""
        line = line.strip()
        if line.upper().startswith('INSERT'):
            return self.identify_table_name(line)
        return None
    
    def _extract_table_name_from_filename(self, file_path: str) -> str:
        """从文件名推断表名"""
        filename = os.path.basename(file_path)
        # 移除扩展名
        table_name = os.path.splitext(filename)[0]
        # 清理特殊字符
        table_name = re.sub(r'[^\w]', '_', table_name)
        return table_name
    
    def _detect_file_encoding(self, file_path: str) -> Dict:
        """
        检测文件编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含编码信息的字典
        """
        try:
            # 读取文件的前面部分进行编码检测
            with open(file_path, 'rb') as f:
                # 读取前100KB用于编码检测
                raw_data = f.read(min(102400, os.path.getsize(file_path)))
                
            result = chardet.detect(raw_data)
            encoding = result.get('encoding', 'utf-8')
            confidence = result.get('confidence', 0.0)
            
            # 常见中文编码映射
            encoding_map = {
                'GB2312': 'gbk',
                'GBK': 'gbk', 
                'gb2312': 'gbk',
                'windows-1252': 'utf-8',  # 很多时候误判
                'ISO-8859-1': 'utf-8'     # 很多时候误判
            }
            
            if encoding in encoding_map:
                original_encoding = encoding
                encoding = encoding_map[encoding]
                self.logger.info(f"编码映射: {original_encoding} -> {encoding}")
            
            return {
                'encoding': encoding or 'utf-8',
                'confidence': confidence,
                'original_encoding': result.get('encoding')
            }
            
        except Exception as e:
            self.logger.warning(f"编码检测失败: {str(e)}，使用默认UTF-8")
            return {
                'encoding': 'utf-8',
                'confidence': 0.5,
                'original_encoding': None
            }
    
    def _extract_with_fallback_encoding(self, file_path: str, progress_callback: Optional[callable] = None) -> Dict:
        """
        使用多种编码尝试提取数据
        
        Args:
            file_path: SQL文件路径
            progress_callback: 进度回调函数
            
        Returns:
            样本数据
        """
        # 常用的中文编码列表
        encodings_to_try = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'big5', 'latin1']
        
        for encoding in encodings_to_try:
            try:
                self.logger.info(f"尝试使用编码: {encoding}")
                
                if progress_callback:
                    progress_callback({
                        'stage': 'encoding_attempt',
                        'message': f'尝试编码: {encoding}',
                        'progress': 5 + encodings_to_try.index(encoding) * 5
                    })
                
                result = self._extract_sample_data_with_encoding(file_path, encoding, progress_callback)
                
                # 检查结果质量
                sample_data = result.get('sample_data', [])
                if self._validate_extracted_data(sample_data):
                    self.logger.info(f"成功使用编码: {encoding}")
                    result['used_encoding'] = encoding
                    return result
                else:
                    self.logger.warning(f"编码 {encoding} 解析结果质量不佳")
                    
            except Exception as e:
                self.logger.warning(f"编码 {encoding} 解析失败: {str(e)}")
                continue
        
        # 所有编码都失败，使用UTF-8并忽略错误
        self.logger.warning("所有编码尝试失败，使用UTF-8并忽略错误")
        return self._extract_sample_data_with_encoding(file_path, 'utf-8', progress_callback, ignore_errors=True)
    
    def _extract_sample_data_with_encoding(self, file_path: str, encoding: str, progress_callback: Optional[callable] = None, ignore_errors: bool = False) -> Dict:
        """
        使用指定编码提取数据
        
        Args:
            file_path: SQL文件路径
            encoding: 文件编码
            progress_callback: 进度回调函数
            ignore_errors: 是否忽略编码错误
            
        Returns:
            样本数据
        """
        errors_mode = 'ignore' if ignore_errors else 'strict'
        
        try:
            file_size = os.path.getsize(file_path)
            self.logger.info(f"使用编码 {encoding} 解析SQL文件: {file_path}, 大小: {file_size / 1024 / 1024:.2f}MB")
            
            if progress_callback:
                progress_callback({
                    'stage': 'file_reading',
                    'message': f'使用 {encoding} 编码读取文件 ({file_size / 1024 / 1024:.2f}MB)',
                    'progress': 10,
                    'file_size': file_size,
                    'encoding': encoding
                })
            
            # 选择解析器
            if self.config.get('parser', {}).get('use_fast_parser', False) and file_size > self.config.get('parser', {}).get('fast_parser_threshold', 50 * 1024 * 1024):
                sample_data = self._extract_with_fast_parser_encoding(file_path, encoding, progress_callback, errors_mode)
            else:
                sample_data = self._extract_with_standard_parser_encoding(file_path, encoding, progress_callback, errors_mode)
            
            if progress_callback:
                progress_callback({
                    'stage': 'extraction_completed',
                    'message': f'解析完成: 表名={sample_data.get("table_name", "未知")}, 样本行数={len(sample_data.get("sample_data", []))}',
                    'progress': 100,
                    'table_name': sample_data.get('table_name', ''),
                    'sample_count': len(sample_data.get('sample_data', [])),
                    'encoding': encoding
                })
            
            return sample_data
            
        except Exception as e:
            self.logger.error(f"使用编码 {encoding} 提取数据失败: {str(e)}")
            if progress_callback:
                progress_callback({
                    'stage': 'extraction_failed',
                    'message': f'编码 {encoding} 提取失败: {str(e)}',
                    'progress': 0,
                    'error': str(e),
                    'encoding': encoding
                })
            raise
    
    def _extract_with_standard_parser_encoding(self, file_path: str, encoding: str, progress_callback: Optional[callable] = None, errors_mode: str = 'strict') -> Dict:
        """
        使用标准解析器和指定编码
        """
        sample_data = []
        table_name = None
        total_lines = 0
        file_size = os.path.getsize(file_path)
        n_lines = self.sample_lines
        
        # 发送解析开始事件
        if progress_callback:
            progress_callback({
                'stage': 'parsing',
                'message': f'开始解析SQL文件: {os.path.basename(file_path)} ({round(file_size / (1024 * 1024), 2)} MB)',
                'progress': 20,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'encoding': encoding
            })
        
        with open(file_path, 'r', encoding=encoding, errors=errors_mode) as f:
            for i, line in enumerate(f):
                total_lines += 1
                
                # 提取样本行
                if i < n_lines:
                    # 清理和转码线条
                    cleaned_line = self._clean_and_normalize_line(line.strip())
                    sample_data.append(cleaned_line)
                    
                    # 尝试识别表名
                    if table_name is None:
                        extracted_table = self._extract_table_name_from_line(cleaned_line)
                        if extracted_table:
                            table_name = extracted_table
                            if progress_callback:
                                progress_callback({
                                    'stage': 'parsing',
                                    'message': f'检测到表名: {table_name}',
                                    'progress': min(70, 20 + (i / n_lines) * 50),
                                    'table_name': table_name,
                                    'encoding': encoding
                                })
                
                # 只统计总行数，不全部读取，但发送进度更新
                if i >= n_lines and i % 50000 == 0:
                    if progress_callback:
                        progress_callback({
                            'stage': 'parsing',
                            'message': f'正在扫描文件，已处理 {i:,} 行',
                            'progress': min(90, 70 + (i / max(file_size / 100, 1)) * 20),
                            'encoding': encoding
                        })
                    continue
                    
        # 如果没有从INSERT语句中提取到表名，尝试从文件名推断
        if table_name is None:
            table_name = self._extract_table_name_from_filename(file_path)
            
        # 估算文件大小和行数
        estimated_rows = self._estimate_total_rows(file_path, sample_data)
        
        self.logger.info(f"成功解析SQL文件: {file_path}, 表名: {table_name}, 样本行数: {len(sample_data)}")
        
        return {
            'file_path': file_path,
            'table_name': table_name,
            'sample_data': sample_data,
            'file_size': file_size,
            'estimated_rows': estimated_rows,
            'total_lines': total_lines,
            'encoding': encoding
        }
    
    def _clean_and_normalize_line(self, line: str) -> str:
        """
        清理和标准化行内容（增强中文字符处理）
        
        Args:
            line: 原始行内容
            
        Returns:
            清理后的行内容
        """
        if not line:
            return line
        
        # 移除BOM标记
        if line.startswith('\ufeff'):
            line = line[1:]
        
        # 标准化引号 - 中文引号转换
        line = line.replace('‘', "'").replace('’', "'")
        line = line.replace('“', '"').replace('”', '"')
        line = line.replace('「', '"').replace('」', '"')  # 日文引号
        line = line.replace('『', '"').replace('』', '"')  # 日文引号
        
        # 标准化中文标点符号
        line = line.replace('，', ',').replace('。', '.')  # 中文逗号句号
        line = line.replace('：', ':').replace('；', ';')  # 中文冒号分号
        line = line.replace('（', '(').replace('）', ')')  # 中文括号
        
        # 清理控制字符，但保留中文字符
        line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', line)
        
        # 规范化空白字符
        line = re.sub(r'\s+', ' ', line)
        
        return line.strip()
    
    def _validate_extracted_data(self, sample_data: List[str]) -> bool:
        """
        验证提取数据的质量（增强中文内容检测）
        
        Args:
            sample_data: 样本数据
            
        Returns:
            数据质量是否合格
        """
        if not sample_data:
            return False
        
        # 检查是否有INSERT语句
        insert_count = 0
        chinese_content_count = 0
        total_lines = len(sample_data)
        
        for line in sample_data:
            line_upper = line.strip().upper()
            if line_upper.startswith('INSERT'):
                insert_count += 1
            
            # 检查是否包含中文字符
            if re.search(r'[\u4e00-\u9fff]+', line):
                chinese_content_count += 1
        
        # 基本质量检查：至少有10%的行是INSERT语句
        has_valid_sql = insert_count > 0 and (insert_count / total_lines) > 0.1
        
        # 如果检测到中文内容，记录日志
        if chinese_content_count > 0:
            self.logger.info(f"检测到中文内容: {chinese_content_count}/{total_lines} 行包含中文字符")
        
        return has_valid_sql
    
    def _estimate_total_rows(self, file_path: str, sample_data: List[str]) -> int:
        """估算总行数"""
        try:
            file_size = os.path.getsize(file_path)
            
            # 计算样本数据的平均行长度
            sample_lines = [line for line in sample_data if line.strip()]
            if not sample_lines:
                return 0
                
            avg_line_length = sum(len(line.encode('utf-8')) for line in sample_lines) / len(sample_lines)
            
            # 估算总行数
            estimated_rows = int(file_size / avg_line_length) if avg_line_length > 0 else 0
            
            return estimated_rows
            
        except Exception as e:
            self.logger.warning(f"估算行数失败: {str(e)}")
            return 0
    
    def _parse_values_string(self, values_str: str) -> List[str]:
        """
        解析VALUES字符串中的值
        这是一个简化版本，复杂情况由AI处理
        """
        values = []
        current_value = ""
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(values_str):
            char = values_str[i]
            
            if char in ("'", '"') and not in_quotes:
                in_quotes = True
                quote_char = char
                current_value += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_value += char
            elif char == ',' and not in_quotes:
                values.append(current_value.strip())
                current_value = ""
            else:
                current_value += char
                
            i += 1
            
        # 添加最后一个值
        if current_value.strip():
            values.append(current_value.strip())
            
        return values