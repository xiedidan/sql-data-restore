"""
高性能SQL文件解析器

使用优化算法提升大文件解析速度
"""

import os
import re
import mmap
import logging
from typing import Dict, List, Optional, Tuple, Generator
from dataclasses import dataclass
import threading
import queue
import time

@dataclass
class ParseResult:
    """解析结果"""
    table_name: Optional[str]
    sample_lines: List[str]
    file_size: int
    estimated_rows: int
    total_lines: int
    parse_time: float

class FastSQLParser:
    """高性能SQL解析器"""
    
    def __init__(self, config: Dict):
        """
        初始化高性能解析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.sample_lines = config.get('migration', {}).get('sample_lines', 100)
        self.chunk_size = config.get('parser', {}).get('chunk_size', 1024 * 1024)  # 1MB chunks
        self.logger = logging.getLogger(__name__)
        
        # 预编译正则表达式
        self.table_name_patterns = [
            re.compile(r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s*\(', re.IGNORECASE),
            re.compile(r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s+VALUES', re.IGNORECASE),
            re.compile(r'INSERT\s+INTO\s+(["`]?)(\w+)\1\s+\(', re.IGNORECASE),
        ]
        
    def extract_sample_data_fast(self, file_path: str, n_lines: Optional[int] = None, 
                                progress_callback: Optional[callable] = None) -> Dict:
        """
        快速提取SQL文件样本数据
        
        Args:
            file_path: SQL文件路径
            n_lines: 要提取的行数
            progress_callback: 进度回调函数
            
        Returns:
            包含表名、样本数据等信息的字典
        """
        start_time = time.time()
        
        if n_lines is None:
            n_lines = self.sample_lines
            
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"SQL文件不存在: {file_path}")
        
        try:
            # 获取文件基本信息
            file_size = os.path.getsize(file_path)
            
            if progress_callback:
                progress_callback({
                    'stage': 'parsing',
                    'message': f'开始快速解析: {os.path.basename(file_path)} ({file_size / (1024 * 1024):.2f} MB)',
                    'progress': 0,
                    'file_size_mb': file_size / (1024 * 1024)
                })
            
            # 根据文件大小选择最佳策略
            if file_size < 10 * 1024 * 1024:  # 小于10MB，使用普通读取
                result = self._parse_small_file(file_path, n_lines, progress_callback)
            else:  # 大文件使用内存映射
                result = self._parse_large_file_mmap(file_path, n_lines, progress_callback)
            
            result.parse_time = time.time() - start_time
            
            if progress_callback:
                progress_callback({
                    'stage': 'parsing_completed',
                    'message': f'快速解析完成: {result.table_name or "unknown"}, 用时 {result.parse_time:.2f}s',
                    'progress': 100,
                    'table_name': result.table_name,
                    'estimated_rows': result.estimated_rows
                })
            
            self.logger.info(f"快速解析完成: {file_path}, 耗时: {result.parse_time:.2f}s")
            
            return {
                'file_path': file_path,
                'table_name': result.table_name,
                'sample_data': result.sample_lines,
                'file_size': result.file_size,
                'estimated_rows': result.estimated_rows,
                'total_lines': result.total_lines,
                'parse_time': result.parse_time
            }
            
        except Exception as e:
            self.logger.error(f"快速解析失败: {file_path}, 错误: {str(e)}")
            if progress_callback:
                progress_callback({
                    'stage': 'parsing_failed',
                    'message': f'快速解析失败: {str(e)}',
                    'progress': 0,
                    'error': str(e)
                })
            raise
    
    def _parse_small_file(self, file_path: str, n_lines: int, 
                         progress_callback: Optional[callable] = None) -> ParseResult:
        """解析小文件（优化版本）"""
        sample_lines = []
        table_name = None
        total_lines = 0
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                total_lines += 1
                
                # 只收集所需的样本行
                if len(sample_lines) < n_lines:
                    stripped_line = line.strip()
                    if stripped_line:  # 跳过空行
                        sample_lines.append(stripped_line)
                        
                        # 尝试提取表名（只在前几行中查找）
                        if table_name is None and len(sample_lines) <= 20:
                            table_name = self._extract_table_name_fast(stripped_line)
                            
                        # 发送进度更新
                        if progress_callback and len(sample_lines) % 20 == 0:
                            progress = min(50, (len(sample_lines) / n_lines) * 50)
                            progress_callback({
                                'stage': 'parsing',
                                'message': f'已收集 {len(sample_lines)} 个样本',
                                'progress': progress,
                                'table_name': table_name
                            })
                
                # 如果已收集足够样本，只计算总行数
                if len(sample_lines) >= n_lines and i % 10000 == 0:
                    if progress_callback:
                        progress = 50 + min(40, (i * 50) / max(file_size / 100, 1))
                        progress_callback({
                            'stage': 'parsing',
                            'message': f'正在计算总行数: {i:,}',
                            'progress': progress
                        })
        
        # 如果没找到表名，从文件名推断
        if table_name is None:
            table_name = self._extract_table_name_from_filename(file_path)
        
        # 快速估算行数
        estimated_rows = self._estimate_rows_fast(file_size, sample_lines)
        
        return ParseResult(
            table_name=table_name,
            sample_lines=sample_lines,
            file_size=file_size,
            estimated_rows=estimated_rows,
            total_lines=total_lines,
            parse_time=0  # 将在外部设置
        )
    
    def _parse_large_file_mmap(self, file_path: str, n_lines: int,
                              progress_callback: Optional[callable] = None) -> ParseResult:
        """使用内存映射解析大文件"""
        sample_lines = []
        table_name = None
        file_size = os.path.getsize(file_path)
        total_lines = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                
                # 快速扫描前几个chunk来收集样本
                chunk_size = min(self.chunk_size, file_size)
                bytes_read = 0
                
                while bytes_read < file_size and len(sample_lines) < n_lines:
                    # 读取chunk
                    chunk_start = bytes_read
                    chunk_end = min(bytes_read + chunk_size, file_size)
                    
                    # 找到合适的行边界
                    if chunk_end < file_size:
                        mmapped_file.seek(chunk_end)
                        while chunk_end < file_size and mmapped_file.read(1) != b'\n':
                            chunk_end += 1
                    
                    # 读取chunk内容
                    mmapped_file.seek(chunk_start)
                    chunk_data = mmapped_file.read(chunk_end - chunk_start).decode('utf-8', errors='ignore')
                    
                    # 处理chunk中的行
                    lines = chunk_data.split('\n')
                    for line in lines:
                        if len(sample_lines) >= n_lines:
                            break
                            
                        stripped_line = line.strip()
                        if stripped_line:
                            sample_lines.append(stripped_line)
                            total_lines += 1
                            
                            # 提取表名
                            if table_name is None and len(sample_lines) <= 20:
                                table_name = self._extract_table_name_fast(stripped_line)
                    
                    bytes_read = chunk_end
                    
                    # 发送进度更新
                    if progress_callback:
                        progress = min(50, (bytes_read / file_size) * 50)
                        progress_callback({
                            'stage': 'parsing',
                            'message': f'已处理 {bytes_read / (1024*1024):.1f}MB, 样本: {len(sample_lines)}',
                            'progress': progress,
                            'table_name': table_name
                        })
                
                # 快速估算总行数（使用内存映射）
                estimated_lines = self._estimate_total_lines_mmap(mmapped_file, progress_callback)
        
        if table_name is None:
            table_name = self._extract_table_name_from_filename(file_path)
        
        return ParseResult(
            table_name=table_name,
            sample_lines=sample_lines,
            file_size=file_size,
            estimated_rows=estimated_lines,
            total_lines=total_lines,
            parse_time=0
        )
    
    def _extract_table_name_fast(self, line: str) -> Optional[str]:
        """快速提取表名（使用预编译正则）"""
        if not line.upper().startswith('INSERT'):
            return None
            
        for pattern in self.table_name_patterns:
            match = pattern.search(line)
            if match:
                return match.group(2)
        return None
    
    def _estimate_rows_fast(self, file_size: int, sample_lines: List[str]) -> int:
        """快速估算行数"""
        if not sample_lines:
            return 0
            
        # 计算平均行字节数
        total_bytes = sum(len(line.encode('utf-8')) + 1 for line in sample_lines[:50])  # +1 for newline
        avg_line_bytes = total_bytes / min(len(sample_lines), 50)
        
        if avg_line_bytes > 0:
            return int(file_size / avg_line_bytes)
        return 0
    
    def _estimate_total_lines_mmap(self, mmapped_file, progress_callback: Optional[callable] = None) -> int:
        """使用内存映射快速估算总行数"""
        file_size = mmapped_file.size()
        
        # 采样策略：读取多个小片段来估算
        sample_size = min(64 * 1024, file_size // 100)  # 64KB或文件的1%
        sample_count = min(10, file_size // sample_size) if sample_size > 0 else 1
        
        total_newlines = 0
        total_sample_bytes = 0
        
        for i in range(sample_count):
            offset = (file_size // sample_count) * i
            mmapped_file.seek(offset)
            
            sample_data = mmapped_file.read(sample_size)
            newlines = sample_data.count(b'\n')
            
            total_newlines += newlines
            total_sample_bytes += len(sample_data)
            
            if progress_callback and i % 3 == 0:
                progress = 50 + ((i + 1) / sample_count) * 40
                progress_callback({
                    'stage': 'parsing',
                    'message': f'正在采样估算行数: {i+1}/{sample_count}',
                    'progress': progress
                })
        
        if total_sample_bytes > 0:
            density = total_newlines / total_sample_bytes
            return int(file_size * density)
        return 0
    
    def _extract_table_name_from_filename(self, file_path: str) -> str:
        """从文件名推断表名"""
        filename = os.path.basename(file_path)
        table_name = os.path.splitext(filename)[0]
        # 清理特殊字符，只保留字母数字和下划线
        table_name = re.sub(r'[^\w]', '_', table_name)
        return table_name


class ThreadedSQLParser:
    """多线程SQL解析器（用于超大文件）"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.sample_lines = config.get('migration', {}).get('sample_lines', 100)
        self.max_workers = config.get('parser', {}).get('max_workers', 4)
        self.logger = logging.getLogger(__name__)
    
    def extract_sample_data_threaded(self, file_path: str, n_lines: Optional[int] = None,
                                   progress_callback: Optional[callable] = None) -> Dict:
        """
        多线程提取样本数据（适用于超大文件）
        
        只在文件大于100MB时使用，否则使用单线程快速解析器
        """
        file_size = os.path.getsize(file_path)
        
        # 小文件直接使用快速解析器
        if file_size < 100 * 1024 * 1024:  # 100MB
            fast_parser = FastSQLParser(self.config)
            return fast_parser.extract_sample_data_fast(file_path, n_lines, progress_callback)
        
        # 大文件使用多线程解析
        return self._parse_with_threads(file_path, n_lines or self.sample_lines, progress_callback)
    
    def _parse_with_threads(self, file_path: str, n_lines: int,
                           progress_callback: Optional[callable] = None) -> Dict:
        """多线程解析实现"""
        start_time = time.time()
        file_size = os.path.getsize(file_path)
        
        if progress_callback:
            progress_callback({
                'stage': 'parsing',
                'message': f'启动多线程解析: {os.path.basename(file_path)}',
                'progress': 0,
                'file_size_mb': file_size / (1024 * 1024)
            })
        
        # 分割文件为多个区域
        workers = min(self.max_workers, 8)  # 最多8个线程
        chunk_size = file_size // workers
        
        sample_queue = queue.Queue()
        table_name_queue = queue.Queue()
        progress_queue = queue.Queue()
        
        # 启动工作线程
        threads = []
        for i in range(workers):
            start_pos = i * chunk_size
            end_pos = (i + 1) * chunk_size if i < workers - 1 else file_size
            
            thread = threading.Thread(
                target=self._worker_parse_chunk,
                args=(file_path, start_pos, end_pos, n_lines // workers + 50, 
                      sample_queue, table_name_queue, progress_queue, i)
            )
            thread.start()
            threads.append(thread)
        
        # 收集结果
        all_samples = []
        table_name = None
        processed_workers = 0
        
        while processed_workers < workers:
            try:
                # 处理进度更新
                try:
                    worker_id, worker_progress = progress_queue.get_nowait()
                    if progress_callback:
                        overall_progress = min(80, (processed_workers * 100 + worker_progress) / workers)
                        progress_callback({
                            'stage': 'parsing',
                            'message': f'多线程解析中: worker {worker_id + 1}/{workers}',
                            'progress': overall_progress
                        })
                except queue.Empty:
                    pass
                
                # 处理样本数据
                try:
                    samples = sample_queue.get_nowait()
                    all_samples.extend(samples)
                    if len(all_samples) >= n_lines:
                        all_samples = all_samples[:n_lines]
                        break
                except queue.Empty:
                    pass
                
                # 处理表名
                try:
                    found_table_name = table_name_queue.get_nowait()
                    if found_table_name and table_name is None:
                        table_name = found_table_name
                except queue.Empty:
                    pass
                
                # 检查线程完成状态
                time.sleep(0.1)
                processed_workers = sum(1 for t in threads if not t.is_alive())
            
            except KeyboardInterrupt:
                # 优雅关闭
                for thread in threads:
                    thread.join(timeout=1)
                raise
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        if table_name is None:
            table_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # 估算总行数
        estimated_rows = self._quick_estimate_lines(file_path)
        
        parse_time = time.time() - start_time
        
        if progress_callback:
            progress_callback({
                'stage': 'parsing_completed',
                'message': f'多线程解析完成: {table_name}, 用时 {parse_time:.2f}s',
                'progress': 100,
                'table_name': table_name,
                'estimated_rows': estimated_rows
            })
        
        return {
            'file_path': file_path,
            'table_name': table_name,
            'sample_data': all_samples,
            'file_size': file_size,
            'estimated_rows': estimated_rows,
            'total_lines': estimated_rows,  # 近似值
            'parse_time': parse_time
        }
    
    def _worker_parse_chunk(self, file_path: str, start_pos: int, end_pos: int, 
                           max_samples: int, sample_queue: queue.Queue, 
                           table_name_queue: queue.Queue, progress_queue: queue.Queue, 
                           worker_id: int):
        """工作线程：解析文件块"""
        try:
            samples = []
            table_name = None
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(start_pos)
                
                # 找到行的开始
                if start_pos > 0:
                    f.readline()  # 跳过可能的不完整行
                
                bytes_read = 0
                chunk_size = end_pos - start_pos
                
                while f.tell() < end_pos and len(samples) < max_samples:
                    line = f.readline()
                    if not line:
                        break
                    
                    stripped_line = line.strip()
                    if stripped_line:
                        samples.append(stripped_line)
                        
                        # 尝试提取表名
                        if table_name is None and len(samples) <= 10:
                            if stripped_line.upper().startswith('INSERT'):
                                # 简化的表名提取
                                match = re.search(r'INSERT\s+INTO\s+(["`]?)(\w+)\1', 
                                                stripped_line, re.IGNORECASE)
                                if match:
                                    table_name = match.group(2)
                                    table_name_queue.put(table_name)
                    
                    # 发送进度
                    bytes_read = f.tell() - start_pos
                    if bytes_read % 50000 == 0:  # 每50KB更新一次
                        progress = (bytes_read / chunk_size) * 100
                        progress_queue.put((worker_id, progress))
            
            # 提交样本数据
            sample_queue.put(samples)
            
        except Exception as e:
            self.logger.error(f"Worker {worker_id} 解析失败: {str(e)}")
    
    def _quick_estimate_lines(self, file_path: str) -> int:
        """快速估算文件行数"""
        try:
            file_size = os.path.getsize(file_path)
            sample_size = min(1024 * 1024, file_size // 10)  # 1MB或文件的10%
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                sample_data = f.read(sample_size)
                lines_in_sample = sample_data.count('\n')
                
                if lines_in_sample > 0:
                    return int((file_size / len(sample_data.encode('utf-8'))) * lines_in_sample)
            return 0
        except:
            return 0