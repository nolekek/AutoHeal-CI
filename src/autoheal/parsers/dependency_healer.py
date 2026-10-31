import os
import re
import tomllib
from typing import Optional, Dict, Any, List

class DependencyHealer:
    """
    Automatically heals MISSING_DEPENDENCY failures by resolving module names
    to PyPI distribution packages and injecting them into pyproject.toml dependencies.
    """

    PACKAGE_NORMALIZATION_MAP: Dict[str, str] = {
        "yaml": "pyyaml",
        "PIL": "pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "bs4": "beautifulsoup4",
        "dotenv": "python-dotenv",
        "jwt": "pyjwt",
        "dateutil": "python-dateutil",
        "Bio": "biopython",
        "magic": "python-magic",
        "psycopg2": "psycopg2-binary",
        "git": "gitpython",
        "OpenGL": "pyopengl",
        "serial": "pyserial",
        "socketio": "python-socketio",
    }

    @classmethod
    def normalize_package(cls, package_name: str) -> str:
        """Normalizes an imported module name to its PyPI package name."""
        if not package_name:
            return ""
        # Strip submodules (e.g., 'yaml.scanner' -> 'yaml')
        root_module = package_name.split(".")[0].strip()
        # Check normalization map
        normalized = cls.PACKAGE_NORMALIZATION_MAP.get(root_module)
        if normalized:
            return normalized
        # Case-insensitive lookup in map
        for k, v in cls.PACKAGE_NORMALIZATION_MAP.items():
            if k.lower() == root_module.lower():
                return v
        return root_module.lower()

    @classmethod
    def can_heal(cls, failure: Any) -> bool:
        """Determines if the failure represents a missing dependency that can be patched."""
        return (
            getattr(failure, "failure_mode", None) == "MISSING_DEPENDENCY"
            and bool(getattr(failure, "missing_package", None))
        )

    @classmethod
    def add_dependency_to_toml_content(
        cls,
        content: str,
        package_name: str,
        version_spec: Optional[str] = None
    ) -> str:
        """
        Injects a package dependency into pyproject.toml content while preserving
        existing formatting, indentation, and comments. Ensures resulting TOML is valid.
        """
        normalized = cls.normalize_package(package_name)
        if not normalized:
            return content

        dep_entry = f"{normalized}{version_spec}" if version_spec else normalized

        # Parse existing TOML to check if already present
        if content.strip():
            try:
                parsed = tomllib.loads(content)
                project_deps = parsed.get("project", {}).get("dependencies", [])
                if isinstance(project_deps, list):
                    for dep in project_deps:
                        clean_dep = re.split(r"[><=~!;\s\[]", str(dep))[0].strip().lower()
                        if clean_dep == normalized.lower():
                            return content  # Already present

                poetry_deps = parsed.get("tool", {}).get("poetry", {}).get("dependencies", {})
                if isinstance(poetry_deps, dict):
                    for dep in poetry_deps.keys():
                        if dep.strip().lower() == normalized.lower():
                            return content  # Already present
            except Exception:
                pass  # Fall back to regex/string patching

        # Case 1: [project] dependencies list exists
        deps_pattern = re.compile(r"(dependencies\s*=\s*\[)(.*?)(\])", re.DOTALL)
        match = deps_pattern.search(content)

        if match:
            prefix = match.group(1)
            inner = match.group(2)
            suffix = match.group(3)

            if "\n" in inner:
                # Multiline list: add new element with indentation
                inner_stripped = inner.rstrip()
                indent = "    "
                lines = [l for l in inner.split("\n") if l.strip()]
                if lines:
                    last_line = lines[-1]
                    indent_match = re.match(r"^(\s*)", last_line)
                    if indent_match and indent_match.group(1):
                        indent = indent_match.group(1)

                if inner_stripped and not inner_stripped.endswith(","):
                    # Add missing comma to preceding item
                    idx = content.rfind(inner_stripped, match.start(), match.end())
                    new_inner = inner_stripped + ",\n" + f'{indent}"{dep_entry}",\n'
                else:
                    new_inner = inner_stripped + "\n" + f'{indent}"{dep_entry}",\n' if inner_stripped else f'\n{indent}"{dep_entry}",\n'

                new_content = content[:match.start()] + prefix + new_inner + suffix + content[match.end():]
            else:
                # Single-line list
                inner_clean = inner.strip()
                if not inner_clean:
                    new_content = content[:match.start()] + f'{prefix}\n    "{dep_entry}",\n{suffix}' + content[match.end():]
                else:
                    new_inner = f'{inner_clean}, "{dep_entry}"'
                    new_content = content[:match.start()] + prefix + " " + new_inner + " " + suffix + content[match.end():]

            # Validate TOML integrity
            try:
                tomllib.loads(new_content)
                return new_content
            except Exception:
                pass

        # Case 2: [project] table exists but without dependencies list
        project_table_pattern = re.compile(r"(^\[project\][^\n]*\n)", re.MULTILINE)
        proj_match = project_table_pattern.search(content)
        if proj_match:
            insert_pos = proj_match.end()
            injection = f'dependencies = [\n    "{dep_entry}",\n]\n'
            new_content = content[:insert_pos] + injection + content[insert_pos:]
            try:
                tomllib.loads(new_content)
                return new_content
            except Exception:
                pass

        # Case 3: [tool.poetry.dependencies] exists
        poetry_table_pattern = re.compile(r"(^\[tool\.poetry\.dependencies\][^\n]*\n)", re.MULTILINE)
        poetry_match = poetry_table_pattern.search(content)
        if poetry_match:
            insert_pos = poetry_match.end()
            poetry_version = f'"{version_spec}"' if version_spec else '"*"'
            injection = f'{normalized} = {poetry_version}\n'
            new_content = content[:insert_pos] + injection + content[insert_pos:]
            try:
                tomllib.loads(new_content)
                return new_content
            except Exception:
                pass

        # Case 4: No [project] section found
        fallback_toml = content.rstrip() + f'\n\n[project]\nname = "autoheal-project"\nversion = "0.1.0"\ndependencies = [\n    "{dep_entry}",\n]\n'
        return fallback_toml.lstrip()

    @classmethod
    def heal_missing_dependency(
        cls,
        pyproject_path: str,
        package_name: str,
        version_spec: Optional[str] = None
    ) -> bool:
        """
        Reads pyproject.toml, injects the missing package dependency, and writes it back.
        Returns True on success, False on failure.
        """
        try:
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = ""

            updated_content = cls.add_dependency_to_toml_content(content, package_name, version_spec)

            # Final syntax guarantee check
            tomllib.loads(updated_content)

            with open(pyproject_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            return True
        except Exception:
            return False

    @classmethod
    def heal_failure(
        cls,
        repo_path: str,
        failure: Any,
        version_spec: Optional[str] = None
    ) -> bool:
        """
        High-level failure handler: extracts the missing package from PytestFailure
        and patches the repo's pyproject.toml.
        """
        if not cls.can_heal(failure):
            return False

        pkg_name = getattr(failure, "missing_package", "")
        if not pkg_name:
            return False

        pyproject_path = os.path.join(repo_path, "pyproject.toml")
        return cls.heal_missing_dependency(pyproject_path, pkg_name, version_spec)
