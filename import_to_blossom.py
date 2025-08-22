import os
import re
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
import pymysql
import markdown
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class NotesImporter:
    def __init__(self):
        self.db_config = {
            'host': os.getenv('MYSQL_HOST'),
            'port': int(os.getenv('MYSQL_PORT')),
            'user': os.getenv('MYSQL_USER'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE'),
            'charset': 'utf8mb4'
        }
        self.image_prefix = os.getenv('IMAGE_PREFIX', '')
        self.notes_dir = Path('./output/note')
        self.images_output_dir = Path('./output/images')
        self.images_output_dir.mkdir(exist_ok=True)
        
        self.connection = None
        self.folder_id_map = {}  # 路径 -> folder_id 映射
        
    def connect_db(self):
        """连接数据库"""
        try:
            self.connection = pymysql.connect(**self.db_config)
            print("数据库连接成功")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            raise
    
    def close_db(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
    
    def get_file_hash(self, file_path):
        """计算文件内容的8位哈希值"""
        with open(file_path, 'rb') as f:
            content = f.read()
            return hashlib.md5(content).hexdigest()[:8]
    
    def parse_metadata(self, content):
        """解析md文件的元数据"""
        if not content.startswith('---\n'):
            return {}, content
        
        try:
            # 找到第二个 ---
            end_idx = content.find('\n---\n', 4)
            if end_idx == -1:
                return {}, content
            
            metadata_text = content[4:end_idx]
            # 移除元数据和后面的换行
            content_without_metadata = content[end_idx + 5:]
            
            metadata = {}
            for line in metadata_text.split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('-'):
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 'tags':
                        # 处理标签列表
                        tags = []
                        continue
                    elif line.startswith('- ') and 'tags' in locals():
                        tags.append(line[2:].strip())
                        metadata['tags'] = tags
                    else:
                        metadata[key] = value
            
            return metadata, content_without_metadata
            
        except Exception as e:
            print(f"解析元数据失败: {e}")
            return {}, content
    
    def process_images_in_content(self, content, md_file_path):
        """处理内容中的图片链接"""
        md_dir = md_file_path.parent
        
        # 匹配图片链接的正则表达式
        img_pattern = r'!\[([^\]]*)\]\((\./images/[^)]+)\)'
        
        def replace_image(match):
            alt_text = match.group(1)
            img_path = match.group(2)
            
            # 构建实际图片文件路径
            actual_img_path = md_dir / img_path.replace('./', '')
            
            if actual_img_path.exists():
                # 获取文件名和扩展名
                img_name = actual_img_path.name
                name_without_ext = actual_img_path.stem
                ext = actual_img_path.suffix
                
                # 计算哈希值
                file_hash = self.get_file_hash(actual_img_path)
                
                # 新文件名
                new_img_name = f"{name_without_ext}_{file_hash}{ext}"
                new_img_path = self.images_output_dir / new_img_name
                
                # 复制图片到输出目录
                try:
                    shutil.copy2(actual_img_path, new_img_path)
                    print(f"图片已复制: {actual_img_path} -> {new_img_path}")
                except Exception as e:
                    print(f"复制图片失败: {e}")
                
                # 返回新的图片链接
                new_link = f"{self.image_prefix}/{new_img_name}"
                return f"![{alt_text}]({new_link})"
            else:
                print(f"图片文件不存在: {actual_img_path}")
                return match.group(0)  # 返回原始链接
        
        return re.sub(img_pattern, replace_image, content)
    
    def create_folder_hierarchy(self):
        """创建文件夹层级结构"""
        cursor = self.connection.cursor()
        
        # 获取所有需要创建的路径
        all_paths = set()
        for md_file in self.notes_dir.rglob('*.md'):
            if '__version_' in md_file.name:
                continue
            
            # 获取相对路径
            relative_path = md_file.relative_to(self.notes_dir)
            path_parts = relative_path.parts[:-1]  # 排除文件名
            
            # 添加所有层级路径
            for i in range(1, len(path_parts) + 1):
                path = '/'.join(path_parts[:i])
                all_paths.add(path)
        
        # 按路径深度排序，确保父文件夹先创建
        sorted_paths = sorted(all_paths, key=lambda x: x.count('/'))
        
        for path in sorted_paths:
            parts = path.split('/')
            folder_name = parts[-1]
            
            if len(parts) == 1:
                # 根文件夹
                pid = 0
            else:
                # 子文件夹
                parent_path = '/'.join(parts[:-1])
                pid = self.folder_id_map.get(parent_path, 0)
            
            # 插入文件夹
            try:
                sql = """
                INSERT INTO blossom_folder 
                (pid, name, icon, tags, open_status, sort, cover, color, describes, 
                 store_path, subject_words, type, user_id, star_status) 
                VALUES (%s, %s, 'wl-folder', '', 0, 1, '', '', '', %s, 0, 1, 1, 0)
                """
                cursor.execute(sql, (pid, folder_name, f'/{path}'))
                folder_id = cursor.lastrowid
                self.folder_id_map[path] = folder_id
                print(f"创建文件夹: {path} (ID: {folder_id})")
                
            except Exception as e:
                print(f"创建文件夹失败 {path}: {e}")
        
        self.connection.commit()
        cursor.close()
    
    def get_word_count(self, content):
        """统计字数（简单实现）"""
        # 移除markdown标记符号，统计中英文字符
        text = re.sub(r'[#*`\[\]()_-]', '', content)
        # 统计中文字符和英文单词
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        return chinese_chars + english_words
    
    def markdown_to_html(self, md_content):
        """将markdown转换为html"""
        try:
            html = markdown.markdown(md_content, extensions=['toc', 'tables', 'codehilite'])
            return html
        except Exception as e:
            print(f"Markdown转HTML失败: {e}")
            return ""
    
    def import_articles(self):
        """导入文章"""
        cursor = self.connection.cursor()
        
        # 获取所有主文件（非版本文件）
        main_files = []
        for md_file in self.notes_dir.rglob('*.md'):
            if '__version_' not in md_file.name:
                main_files.append(md_file)
        
        # 按文件夹分组，用于计算sort值
        folder_files = {}
        for md_file in main_files:
            relative_path = md_file.relative_to(self.notes_dir)
            folder_path = '/'.join(relative_path.parts[:-1]) if len(relative_path.parts) > 1 else ''
            
            if folder_path not in folder_files:
                folder_files[folder_path] = []
            folder_files[folder_path].append(md_file)
        
        # 为每个文件夹的文件按创建时间排序
        for folder_path, files in folder_files.items():
            # 读取每个文件的创建时间
            files_with_time = []
            for md_file in files:
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    metadata, _ = self.parse_metadata(content)
                    cre_time_str = metadata.get('CREATE_TIME', '2000-01-01 00:00:00')
                    cre_time = datetime.strptime(cre_time_str, '%Y-%m-%d %H:%M:%S')
                    files_with_time.append((md_file, cre_time))
                except:
                    files_with_time.append((md_file, datetime(2000, 1, 1)))
            
            # 按创建时间排序
            files_with_time.sort(key=lambda x: x[1])
            folder_files[folder_path] = files_with_time
        
        # 导入文章
        article_id_map = {}  # file_path -> article_id
        
        for folder_path, files_with_time in folder_files.items():
            # 获取文件夹ID
            pid = self.folder_id_map.get(folder_path, 0)
            
            for sort_index, (md_file, _) in enumerate(files_with_time, 1):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    metadata, content_without_metadata = self.parse_metadata(content)
                    
                    # 处理图片链接
                    processed_content = self.process_images_in_content(content_without_metadata, md_file)
                    
                    # 提取信息
                    name = md_file.stem
                    tags = ','.join(metadata.get('tags', []))
                    cre_time_str = metadata.get('CREATE_TIME', '2000-01-01 00:00:00')
                    upd_time_str = metadata.get('UPDATE_TIME', cre_time_str)
                    
                    cre_time = datetime.strptime(cre_time_str, '%Y-%m-%d %H:%M:%S')
                    upd_time = datetime.strptime(upd_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    words = self.get_word_count(processed_content)
                    html = self.markdown_to_html(processed_content)
                    
                    # 插入文章
                    sql = """
                    INSERT INTO blossom_article 
                    (pid, name, icon, tags, sort, cover, describes, star_status, open_status, 
                     open_version, pv, uv, likes, words, version, color, toc, markdown, html, 
                     cre_time, upd_time, user_id, upd_markdown_time) 
                    VALUES (%s, %s, '', %s, %s, '', '', 0, 0, 0, 0, 0, 0, %s, 0, '', '', %s, %s, 
                            %s, %s, 1, %s)
                    """
                    cursor.execute(sql, (
                        pid, name, tags, sort_index, words, processed_content, html,
                        cre_time, upd_time, upd_time
                    ))
                    
                    article_id = cursor.lastrowid
                    article_id_map[str(md_file)] = article_id
                    print(f"导入文章: {name} (ID: {article_id})")
                    
                except Exception as e:
                    print(f"导入文章失败 {md_file}: {e}")
        
        self.connection.commit()
        cursor.close()
        return article_id_map
    
    def import_article_versions(self, article_id_map):
        """导入文章版本"""
        cursor = self.connection.cursor()
        
        # 获取所有版本文件
        version_files = list(self.notes_dir.rglob('*__version_*.md'))
        
        # 按主文件分组
        version_groups = {}
        for version_file in version_files:
            # 从文件名提取主文件名和版本时间
            match = re.match(r'(.+)__version_(\d+)\.md$', version_file.name)
            if match:
                main_name = match.group(1)
                version_timestamp = int(match.group(2))
                
                # 构建主文件路径
                main_file_path = version_file.parent / f"{main_name}.md"
                
                if str(main_file_path) not in version_groups:
                    version_groups[str(main_file_path)] = []
                
                version_groups[str(main_file_path)].append((version_file, version_timestamp))
        
        # 导入版本
        for main_file_path, versions in version_groups.items():
            article_id = article_id_map.get(main_file_path)
            if not article_id:
                print(f"找不到主文章ID: {main_file_path}")
                continue
            
            # 导入历史版本
            for version_file, version_timestamp in versions:
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    _, content_without_metadata = self.parse_metadata(content)
                    # 处理图片链接
                    processed_content = self.process_images_in_content(
                        content_without_metadata, version_file
                    )
                    
                    # 转换时间戳
                    cre_time = datetime.fromtimestamp(version_timestamp / 1000)
                    
                    sql = """
                    INSERT INTO blossom_article_log (article_id, version, markdown, cre_time)
                    VALUES (%s, 0, %s, %s)
                    """
                    cursor.execute(sql, (article_id, processed_content, cre_time))
                    print(f"导入版本: {version_file.name} -> 文章ID {article_id}")
                    
                except Exception as e:
                    print(f"导入版本失败 {version_file}: {e}")
            
            # 导入当前版本（主文件）
            try:
                main_file = Path(main_file_path)
                if main_file.exists():
                    with open(main_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    metadata, content_without_metadata = self.parse_metadata(content)
                    processed_content = self.process_images_in_content(
                        content_without_metadata, main_file
                    )
                    
                    upd_time_str = metadata.get('UPDATE_TIME', '2000-01-01 00:00:00')
                    upd_time = datetime.strptime(upd_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    sql = """
                    INSERT INTO blossom_article_log (article_id, version, markdown, cre_time)
                    VALUES (%s, 0, %s, %s)
                    """
                    cursor.execute(sql, (article_id, processed_content, upd_time))
                    print(f"导入当前版本: {main_file.name} -> 文章ID {article_id}")
                    
            except Exception as e:
                print(f"导入当前版本失败 {main_file_path}: {e}")
        
        self.connection.commit()
        cursor.close()
    
    def run(self):
        """运行导入流程"""
        try:
            print("开始导入笔记...")
            
            # 连接数据库
            self.connect_db()
            
            # 创建文件夹层级
            print("\n1. 创建文件夹层级...")
            self.create_folder_hierarchy()
            
            # 导入文章
            print("\n2. 导入文章...")
            article_id_map = self.import_articles()
            
            # 导入版本
            print("\n3. 导入文章版本...")
            self.import_article_versions(article_id_map)
            
            print("\n导入完成！")
            
        except Exception as e:
            print(f"导入过程中发生错误: {e}")
            raise
        finally:
            self.close_db()

if __name__ == '__main__':
    importer = NotesImporter()
    importer.run()