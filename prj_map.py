import os
import fnmatch

def load_gitignore(root_dir):
    """
    加载项目根目录下的 .gitignore 文件规则
    """
    ignore_patterns =['.git', '__pycache__', '*.pyc', '.venv', 'venv', '.idea', '.vscode']
    gitignore_path = os.path.join(root_dir, '.gitignore')
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 去掉目录后缀的斜杠以便于 fnmatch 匹配
                    if line.endswith('/'):
                        line = line[:-1]
                    ignore_patterns.append(line)
    return ignore_patterns

def is_ignored(name, ignore_patterns):
    """
    使用 fnmatch 判断当前文件/目录是否在忽略列表中
    """
    for pattern in ignore_patterns:
        # 匹配自身或以该模式开头的项
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name, pattern + '*'):
            return True
    return False

def generate_tree(dir_path, prefix='', ignore_patterns=None):
    """
    递归遍历并打印树状结构
    """
    if ignore_patterns is None:
        ignore_patterns =[]

    try:
        items = os.listdir(dir_path)
    except PermissionError:
        return

    # 过滤掉不需要关注的文件和目录
    items = [item for item in items if not is_ignored(item, ignore_patterns)]
    
    # 排序：让文件夹在上方，文件在下方，同类按字母排序
    items.sort(key=lambda x: (not os.path.isdir(os.path.join(dir_path, x)), x))

    count = len(items)
    for i, item in enumerate(items):
        is_last = (i == count - 1)
        item_path = os.path.join(dir_path, item)
        is_dir = os.path.isdir(item_path)

        # 确定当前的连接符和图标
        connector = '┗ ' if is_last else '┣ '
        icon = '📂 ' if is_dir else '📜 '
        
        print(f"{prefix}{connector}{icon}{item}")

        # 如果是目录，则深入递归
        if is_dir:
            extension = '  ' if is_last else '┃ '
            generate_tree(item_path, prefix + extension, ignore_patterns)

if __name__ == '__main__':
    root_directory = '.'  # 指向当前脚本所在的根目录
    project_name = os.path.basename(os.path.abspath(root_directory))
    
    print(f"📦 {project_name}")
    patterns = load_gitignore(root_directory)
    generate_tree(root_directory, ignore_patterns=patterns)