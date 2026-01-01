#!/usr/bin/env python3
"""
プロジェクト進捗確認用 コードベース収集スクリプト

目的: PDFなどの巨大ファイルを除外し、
      実際に動いているコード（.py, .md, .txt等）のみを
      1つのテキストファイルにまとめて進捗確認可能にする

出力: project_codebase_YYYYMMDD_HHMMSS.md
"""

import os
import datetime
from pathlib import Path
from collections import defaultdict

# 収集対象の拡張子
INCLUDE_EXTENSIONS = {
    '.py', '.md', '.txt', '.json', '.yaml', '.yml', 
    '.toml', '.ini', '.cfg', '.sh', '.env.example'
}

# 除外するディレクトリ
EXCLUDE_DIRS = {
    '__pycache__', '.git', 'venv', 'env', '.venv', 
    'node_modules', '.pytest_cache', '.mypy_cache',
    'data', 'logs', 'temp', 'tmp'
}

# 除外するファイル
EXCLUDE_FILES = {
    '.env', '.DS_Store', 'Thumbs.db', '*.pyc', '*.pyo',
    '*.log', '*.db', '*.sqlite', '*.pdf'
}

class CodebaseCollector:
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.files_collected = []
        self.stats = defaultdict(int)
        
    def should_include_dir(self, dir_path: Path) -> bool:
        """ディレクトリを収集対象にするか判定"""
        dir_name = dir_path.name
        return dir_name not in EXCLUDE_DIRS and not dir_name.startswith('.')
    
    def should_include_file(self, file_path: Path) -> bool:
        """ファイルを収集対象にするか判定"""
        # .envファイルを確実に除外（.env, .env.local, .env.production など）
        if file_path.name.startswith('.env'):
            return False

        # 拡張子チェック
        if file_path.suffix not in INCLUDE_EXTENSIONS:
            return False

        # 除外ファイル名チェック
        if file_path.name in EXCLUDE_FILES:
            return False

        # ファイルサイズチェック（1MB以上は除外）
        try:
            if file_path.stat().st_size > 1_000_000:
                return False
        except:
            return False

        return True
    
    def collect_files(self):
        """ファイル一覧を収集"""
        for item in self.root.rglob('*'):
            if item.is_file() and self.should_include_file(item):
                # 親ディレクトリが除外対象でないかチェック
                if all(self.should_include_dir(parent) for parent in item.parents if parent != self.root):
                    self.files_collected.append(item)
                    self.stats['total_files'] += 1
                    self.stats[f'ext_{item.suffix}'] += 1
    
    def generate_tree(self) -> str:
        """ディレクトリツリーを生成"""
        tree_lines = [f"# 📁 プロジェクト構造\n\n```"]
        tree_lines.append(f"{self.root.name}/")
        
        # ディレクトリ構造を辞書で整理
        dir_structure = defaultdict(list)
        for file_path in sorted(self.files_collected):
            rel_path = file_path.relative_to(self.root)
            parent = rel_path.parent
            dir_structure[str(parent)].append(rel_path.name)
        
        # ツリー形式で出力
        for dir_path in sorted(dir_structure.keys()):
            if dir_path == '.':
                prefix = "├── "
            else:
                depth = len(Path(dir_path).parts)
                prefix = "│   " * depth + "├── "
                tree_lines.append("│   " * (depth - 1) + f"├── {Path(dir_path).parts[-1]}/")
            
            for filename in sorted(dir_structure[dir_path]):
                tree_lines.append(prefix + filename)
        
        tree_lines.append("```\n")
        return "\n".join(tree_lines)
    
    def count_lines(self, file_path: Path) -> int:
        """ファイルの行数をカウント"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return len(f.readlines())
        except:
            return 0
    
    def generate_file_contents(self) -> str:
        """ファイル内容を生成"""
        contents = ["\n# 📄 ファイル内容\n"]
        
        # Pythonファイルを優先的に表示
        py_files = [f for f in self.files_collected if f.suffix == '.py']
        other_files = [f for f in self.files_collected if f.suffix != '.py']
        
        for file_list, category in [(py_files, "Python Scripts"), (other_files, "Configuration & Documentation")]:
            if file_list:
                contents.append(f"\n## {category}\n")
                
                for file_path in sorted(file_list):
                    rel_path = file_path.relative_to(self.root)
                    lines = self.count_lines(file_path)
                    self.stats['total_lines'] += lines
                    
                    contents.append(f"\n### 📝 `{rel_path}` ({lines} lines)\n")
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # コードブロックで囲む
                        if file_path.suffix == '.py':
                            contents.append(f"```python\n{content}\n```\n")
                        elif file_path.suffix == '.json':
                            contents.append(f"```json\n{content}\n```\n")
                        elif file_path.suffix in {'.yaml', '.yml'}:
                            contents.append(f"```yaml\n{content}\n```\n")
                        elif file_path.suffix == '.sh':
                            contents.append(f"```bash\n{content}\n```\n")
                        else:
                            contents.append(f"```\n{content}\n```\n")
                            
                    except Exception as e:
                        contents.append(f"```\n[読み込みエラー: {e}]\n```\n")
        
        return "\n".join(contents)
    
    def generate_statistics(self) -> str:
        """統計情報を生成"""
        stats_lines = ["\n# 📊 統計情報\n"]
        stats_lines.append(f"- **総ファイル数**: {self.stats['total_files']}")
        stats_lines.append(f"- **総行数**: {self.stats['total_lines']}")
        stats_lines.append(f"\n## ファイル種別\n")
        
        for key, value in sorted(self.stats.items()):
            if key.startswith('ext_'):
                ext = key.replace('ext_', '')
                stats_lines.append(f"- `{ext}`: {value}ファイル")
        
        return "\n".join(stats_lines)
    
    def generate_report(self) -> str:
        """完全なレポートを生成"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = [
            f"# 🔍 プロジェクトコードベース全体像\n",
            f"**生成日時**: {timestamp}",
            f"**ルートディレクトリ**: `{self.root.absolute()}`\n",
            "---\n"
        ]
        
        # ディレクトリツリー
        report.append(self.generate_tree())
        
        # 統計情報
        report.append(self.generate_statistics())
        
        # ファイル内容
        report.append(self.generate_file_contents())
        
        return "\n".join(report)
    
    def save_report(self, output_path: Path = None):
        """レポートをファイルに保存"""
        if output_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.root / f"project_codebase_{timestamp}.md"
        
        print(f"📂 コードベース収集中: {self.root}")
        self.collect_files()
        print(f"✅ {self.stats['total_files']}ファイルを収集")
        
        print(f"📝 レポート生成中...")
        report = self.generate_report()
        
        print(f"💾 保存中: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 完了!")
        print(f"📄 ファイルサイズ: {output_path.stat().st_size / 1024:.1f} KB")
        print(f"📊 総行数: {self.stats['total_lines']:,}")
        
        return output_path


def main():
    import sys
    
    # コマンドライン引数からプロジェクトルートを取得
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        # 引数がない場合は現在のディレクトリ
        project_root = "."
    
    collector = CodebaseCollector(project_root)
    output_file = collector.save_report()
    
    print(f"\n🎉 進捗確認用ファイルが作成されました:")
    print(f"   {output_file.absolute()}")
    print(f"\nこのファイルをAI models (Gemini, OpenAI, Anthropic)に渡すことで、")
    print(f"プロジェクト全体の進捗状況を詳細に把握できます。")


if __name__ == "__main__":
    main()
