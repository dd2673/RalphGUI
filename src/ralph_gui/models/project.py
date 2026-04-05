"""
项目模型
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Project:
    """项目模型"""
    directory: Path
    name: str = ""
    is_ralph_enabled: bool = False
    prompt_file: Optional[Path] = None
    fix_plan_file: Optional[Path] = None
    agent_file: Optional[Path] = None
    ralphrc_file: Optional[Path] = None
    ralph_dir: Optional[Path] = None

    # Ralph 配置文件路径
    RALPH_DIR: str = ".ralph"
    PROMPT_FILE: str = "PROMPT.md"
    FIX_PLAN_FILE: str = "fix_plan.md"
    AGENT_FILE: str = "AGENT.md"
    RALPHRC_FILE: str = ".ralphrc"

    @classmethod
    def from_directory(cls, directory: Path) -> "Project":
        """从目录创建项目模型"""
        project = cls(directory=directory)
        project.name = directory.name
        project.ralph_dir = directory / cls.RALPH_DIR

        # 检查必要的文件
        project.prompt_file = project.ralph_dir / cls.PROMPT_FILE if project.ralph_dir.exists() else None
        project.fix_plan_file = project.ralph_dir / cls.FIX_PLAN_FILE if project.ralph_dir.exists() else None
        project.agent_file = project.ralph_dir / cls.AGENT_FILE if project.ralph_dir.exists() else None
        project.ralphrc_file = directory / cls.RALPHRC_FILE

        project.is_ralph_enabled = all([
            project.ralph_dir and project.ralph_dir.exists(),
            project.prompt_file and project.prompt_file.exists(),
            project.fix_plan_file and project.fix_plan_file.exists(),
            project.agent_file and project.agent_file.exists(),
        ])

        return project

    def has_git(self) -> bool:
        """检查是否是Git仓库"""
        return (self.directory / ".git").exists()

    def get_config(self, key: str, default=None):
        """从.ralphrc获取配置"""
        if not self.ralphrc_file or not self.ralphrc_file.exists():
            return default
        try:
            with open(self.ralphrc_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith(key):
                        _, _, value = line.partition("=")
                        return value.strip()
        except IOError:
            pass
        return default
