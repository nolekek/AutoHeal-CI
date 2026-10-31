import os
from typing import Optional, List, Tuple
from pydantic import BaseModel
import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python

class ASTSliceResult(BaseModel):
    file_path: str
    symbol_name: str
    symbol_type: str                   # 'function', 'method', or 'module_level'
    start_line: int                    # 1-indexed
    end_line: int                      # 1-indexed
    code: str                          # Exact source code of the function/method
    enclosing_class: Optional[str] = None
    neighboring_signatures: List[str] = []

class PythonASTSlicer:
    """Uses Tree-sitter to perform AST-aware call-graph and symbol slicing."""

    def __init__(self):
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)

    def slice_at_line(self, file_path: str, line_number: int) -> Optional[ASTSliceResult]:
        """
        Locates the smallest enclosing function/method definition around line_number (1-indexed).
        """
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as f:
            source_bytes = f.read()

        tree = self.parser.parse(source_bytes)
        root_node = tree.root_node

        # Target line 0-indexed for tree-sitter
        target_row = max(0, line_number - 1)
        target_point = (target_row, 0)

        # Find enclosing function node
        func_node, class_node = self._find_enclosing_nodes(root_node, target_row)

        if func_node is None:
            # Fallback to window around target line if no function found (e.g. module level)
            return self._module_level_slice(file_path, source_bytes, target_row)

        # Extract function name
        name_node = func_node.child_by_field_name("name")
        func_name = name_node.text.decode("utf-8") if name_node else "anonymous"

        # Check if inside class
        class_name = None
        signatures = []
        symbol_type = "function"

        if class_node:
            symbol_type = "method"
            cname_node = class_node.child_by_field_name("name")
            class_name = cname_node.text.decode("utf-8") if cname_node else "AnonymousClass"
            signatures = self._extract_class_signatures(class_node, exclude_func_name=func_name)

        start_line = func_node.start_point[0] + 1
        end_line = func_node.end_point[0] + 1
        code_slice = func_node.text.decode("utf-8")

        return ASTSliceResult(
            file_path=file_path,
            symbol_name=func_name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
            code=code_slice,
            enclosing_class=class_name,
            neighboring_signatures=signatures
        )

    def slice_function_by_name(self, file_path: str, function_name: str) -> Optional[ASTSliceResult]:
        """Finds a function by its identifier name in a file."""
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as f:
            source_bytes = f.read()

        tree = self.parser.parse(source_bytes)
        func_node, class_node = self._find_function_by_name(tree.root_node, function_name)

        if not func_node:
            return None

        class_name = None
        symbol_type = "function"
        signatures = []

        if class_node:
            symbol_type = "method"
            cname_node = class_node.child_by_field_name("name")
            class_name = cname_node.text.decode("utf-8") if cname_node else None
            signatures = self._extract_class_signatures(class_node, exclude_func_name=function_name)

        start_line = func_node.start_point[0] + 1
        end_line = func_node.end_point[0] + 1
        code_slice = func_node.text.decode("utf-8")

        return ASTSliceResult(
            file_path=file_path,
            symbol_name=function_name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
            code=code_slice,
            enclosing_class=class_name,
            neighboring_signatures=signatures
        )

    def _find_enclosing_nodes(self, root: tree_sitter.Node, target_row: int) -> Tuple[Optional[tree_sitter.Node], Optional[tree_sitter.Node]]:
        """Walks down to find the tightest function_definition containing target_row."""
        curr = root
        deepest_func = None
        enclosing_class = None

        def visit(node: tree_sitter.Node, current_class: Optional[tree_sitter.Node]):
            nonlocal deepest_func, enclosing_class
            node_type = node.type
            new_class = current_class

            if node_type == "class_definition":
                new_class = node

            if node_type in ("function_definition", "async_function_definition"):
                start_row = node.start_point[0]
                end_row = node.end_point[0]
                if start_row <= target_row <= end_row:
                    deepest_func = node
                    enclosing_class = new_class

            for child in node.children:
                visit(child, new_class)

        visit(root, None)
        return deepest_func, enclosing_class

    def _find_function_by_name(self, root: tree_sitter.Node, target_name: str) -> Tuple[Optional[tree_sitter.Node], Optional[tree_sitter.Node]]:
        found_func = None
        found_class = None

        def visit(node: tree_sitter.Node, current_class: Optional[tree_sitter.Node]):
            nonlocal found_func, found_class
            if found_func:
                return

            new_class = node if node.type == "class_definition" else current_class

            if node.type in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                if name_node and name_node.text.decode("utf-8") == target_name:
                    found_func = node
                    found_class = new_class
                    return

            for child in node.children:
                visit(child, new_class)

        visit(root, None)
        return found_func, found_class

    def _extract_class_signatures(self, class_node: tree_sitter.Node, exclude_func_name: str) -> List[str]:
        signatures = []
        body_node = class_node.child_by_field_name("body")
        if not body_node:
            return signatures

        for child in body_node.children:
            if child.type in ("function_definition", "async_function_definition"):
                name_node = child.child_by_field_name("name")
                fname = name_node.text.decode("utf-8") if name_node else ""
                if fname and fname != exclude_func_name:
                    params_node = child.child_by_field_name("parameters")
                    return_type_node = child.child_by_field_name("return_type")
                    params_text = params_node.text.decode("utf-8") if params_node else "()"
                    ret_text = f" -> {return_type_node.text.decode('utf-8')}" if return_type_node else ""
                    signatures.append(f"def {fname}{params_text}{ret_text}: ...")
        return signatures

    def _module_level_slice(self, file_path: str, source_bytes: bytes, target_row: int) -> ASTSliceResult:
        lines = source_bytes.decode("utf-8", errors="replace").splitlines()
        start = max(0, target_row - 10)
        end = min(len(lines), target_row + 11)
        code = "\n".join(lines[start:end])
        return ASTSliceResult(
            file_path=file_path,
            symbol_name="<module>",
            symbol_type="module_level",
            start_line=start + 1,
            end_line=end,
            code=code,
            enclosing_class=None,
            neighboring_signatures=[]
        )
