import os
from typing import Optional, List, Tuple
from pydantic import BaseModel
import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python

class ASTSliceResult(BaseModel):
    file_path: str
    symbol_name: str
    symbol_type: str                   # 'function', 'async_function', 'method', or 'module_level'
    start_line: int                    # 1-indexed
    end_line: int                      # 1-indexed
    code: str                          # Exact source code of the function/method (including decorators)
    enclosing_class: Optional[str] = None
    decorators: List[str] = []
    neighboring_signatures: List[str] = []

class PythonASTSlicer:
    """Uses Tree-sitter to perform AST-aware call-graph, decorator-aware, and symbol slicing."""

    def __init__(self):
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)

    def slice_at_line(self, file_path: str, line_number: int) -> Optional[ASTSliceResult]:
        """
        Locates the smallest enclosing function/method definition around line_number (1-indexed),
        capturing associated decorators and enclosing class context.
        """
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as f:
            source_bytes = f.read()

        tree = self.parser.parse(source_bytes)
        root_node = tree.root_node

        target_row = max(0, line_number - 1)
        func_node, class_node, outer_decorated = self._find_enclosing_nodes(root_node, target_row)

        if func_node is None:
            return self._module_level_slice(file_path, source_bytes, target_row)

        # Use the outer decorated node for slice boundaries if present
        target_slice_node = outer_decorated if outer_decorated is not None else func_node

        name_node = func_node.child_by_field_name("name")
        func_name = name_node.text.decode("utf-8") if name_node else "anonymous"

        class_name = None
        signatures = []
        is_async = any(c.type == "async" for c in func_node.children)
        symbol_type = "async_function" if is_async else "function"

        if class_node:
            symbol_type = "async_method" if is_async else "method"
            cname_node = class_node.child_by_field_name("name")
            class_name = cname_node.text.decode("utf-8") if cname_node else "AnonymousClass"
            signatures = self._extract_class_signatures(class_node, exclude_func_name=func_name)

        decorators = self._extract_decorators(outer_decorated) if outer_decorated else []

        start_line = target_slice_node.start_point[0] + 1
        end_line = target_slice_node.end_point[0] + 1
        code_slice = target_slice_node.text.decode("utf-8")

        return ASTSliceResult(
            file_path=file_path,
            symbol_name=func_name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
            code=code_slice,
            enclosing_class=class_name,
            decorators=decorators,
            neighboring_signatures=signatures
        )

    def slice_function_by_name(self, file_path: str, function_name: str) -> Optional[ASTSliceResult]:
        """Finds a function by identifier name, preserving decorators."""
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as f:
            source_bytes = f.read()

        tree = self.parser.parse(source_bytes)
        func_node, class_node, outer_decorated = self._find_function_by_name(tree.root_node, function_name)

        if not func_node:
            return None

        target_slice_node = outer_decorated if outer_decorated is not None else func_node

        class_name = None
        signatures = []
        is_async = any(c.type == "async" for c in func_node.children)
        symbol_type = "async_function" if is_async else "function"

        if class_node:
            symbol_type = "async_method" if is_async else "method"
            cname_node = class_node.child_by_field_name("name")
            class_name = cname_node.text.decode("utf-8") if cname_node else None
            signatures = self._extract_class_signatures(class_node, exclude_func_name=function_name)

        decorators = self._extract_decorators(outer_decorated) if outer_decorated else []

        start_line = target_slice_node.start_point[0] + 1
        end_line = target_slice_node.end_point[0] + 1
        code_slice = target_slice_node.text.decode("utf-8")

        return ASTSliceResult(
            file_path=file_path,
            symbol_name=function_name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
            code=code_slice,
            enclosing_class=class_name,
            decorators=decorators,
            neighboring_signatures=signatures
        )

    def _find_enclosing_nodes(
        self, root: tree_sitter.Node, target_row: int
    ) -> Tuple[Optional[tree_sitter.Node], Optional[tree_sitter.Node], Optional[tree_sitter.Node]]:
        deepest_func = None
        enclosing_class = None
        outer_decorated = None

        def visit(node: tree_sitter.Node, current_class: Optional[tree_sitter.Node], current_decorated: Optional[tree_sitter.Node]):
            nonlocal deepest_func, enclosing_class, outer_decorated
            node_type = node.type
            new_class = node if node_type == "class_definition" else current_class
            new_decorated = node if node_type == "decorated_definition" else current_decorated

            if node_type in ("function_definition", "async_function_definition"):
                start_row = node.start_point[0]
                end_row = node.end_point[0]
                # If wrapped in decorated_definition, expand start_row to include decorators
                if new_decorated and new_decorated.children and node in new_decorated.children:
                    start_row = new_decorated.start_point[0]

                if start_row <= target_row <= end_row:
                    deepest_func = node
                    enclosing_class = new_class
                    outer_decorated = new_decorated

            for child in node.children:
                visit(child, new_class, new_decorated)

        visit(root, None, None)
        return deepest_func, enclosing_class, outer_decorated

    def _find_function_by_name(
        self, root: tree_sitter.Node, target_name: str
    ) -> Tuple[Optional[tree_sitter.Node], Optional[tree_sitter.Node], Optional[tree_sitter.Node]]:
        found_func = None
        found_class = None
        found_decorated = None

        def visit(node: tree_sitter.Node, current_class: Optional[tree_sitter.Node], current_decorated: Optional[tree_sitter.Node]):
            nonlocal found_func, found_class, found_decorated
            if found_func:
                return

            new_class = node if node.type == "class_definition" else current_class
            new_decorated = node if node.type == "decorated_definition" else current_decorated

            if node.type in ("function_definition", "async_function_definition"):
                name_node = node.child_by_field_name("name")
                if name_node and name_node.text.decode("utf-8") == target_name:
                    found_func = node
                    found_class = new_class
                    found_decorated = new_decorated
                    return

            for child in node.children:
                visit(child, new_class, new_decorated)

        visit(root, None, None)
        return found_func, found_class, found_decorated

    def _extract_decorators(self, decorated_node: tree_sitter.Node) -> List[str]:
        decorators = []
        for child in decorated_node.children:
            if child.type == "decorator":
                decorators.append(child.text.decode("utf-8"))
        return decorators

    def _extract_class_signatures(self, class_node: tree_sitter.Node, exclude_func_name: str) -> List[str]:
        signatures = []
        body_node = class_node.child_by_field_name("body")
        if not body_node:
            return signatures

        for child in body_node.children:
            fn_node = child
            if child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in ("function_definition", "async_function_definition"):
                        fn_node = sub
                        break

            if fn_node.type in ("function_definition", "async_function_definition"):
                name_node = fn_node.child_by_field_name("name")
                fname = name_node.text.decode("utf-8") if name_node else ""
                if fname and fname != exclude_func_name:
                    params_node = fn_node.child_by_field_name("parameters")
                    return_type_node = fn_node.child_by_field_name("return_type")
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
            decorators=[],
            neighboring_signatures=[]
        )
