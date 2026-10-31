import os
from typing import Optional, List, Tuple
import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_typescript

from .ast_slicer import ASTSliceResult


class _Candidate:
    """Represents a discovered function, arrow function, or method candidate in the AST."""

    def __init__(
        self,
        core_node: tree_sitter.Node,
        slice_node: Optional[tree_sitter.Node],
        symbol_name: str,
        symbol_type: str,
        start_byte: int,
        end_byte: int,
        start_row: int,
        end_row: int,
        enclosing_class_node: Optional[tree_sitter.Node] = None,
        enclosing_class_name: Optional[str] = None,
        decorators: Optional[List[str]] = None,
    ):
        self.core_node = core_node
        self.slice_node = slice_node
        self.symbol_name = symbol_name
        self.symbol_type = symbol_type
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.start_row = start_row
        self.end_row = end_row
        self.enclosing_class_node = enclosing_class_node
        self.enclosing_class_name = enclosing_class_name
        self.decorators = decorators or []
        self.span = end_byte - start_byte


class TypeScriptASTSlicer:
    """Uses Tree-sitter (tree-sitter-typescript) to perform AST-aware slicing

    for TypeScript and JavaScript source files (.ts, .tsx, .js, .jsx).
    """

    def __init__(self):
        self.ts_language = Language(tree_sitter_typescript.language_typescript())
        self.ts_parser = Parser(self.ts_language)
        self.tsx_language = Language(tree_sitter_typescript.language_tsx())
        self.tsx_parser = Parser(self.tsx_language)

    def get_parser(self, file_path: str = "") -> Parser:
        """Returns TSX parser for .tsx/.jsx files or standard TS parser otherwise."""
        ext = os.path.splitext(file_path)[1].lower() if file_path else ""
        if ext in (".tsx", ".jsx"):
            return self.tsx_parser
        return self.ts_parser

    def parse_source(self, source_bytes: bytes, file_path: str = "temp.ts") -> tree_sitter.Tree:
        """Parses source bytes, with intelligent fallback to TSX if the standard TS parser

        encounters syntax errors (such as embedded JSX tags in .js/.ts files).
        """
        parser = self.get_parser(file_path)
        tree = parser.parse(source_bytes)
        if parser is self.ts_parser and tree.root_node.has_error:
            tsx_tree = self.tsx_parser.parse(source_bytes)
            if not tsx_tree.root_node.has_error:
                return tsx_tree
        return tree

    def slice_at_line(self, file_path: str, line_number: int) -> Optional[ASTSliceResult]:
        """Locates the smallest enclosing function, arrow function, or method definition

        around line_number (1-indexed), capturing decorators, enclosing class, and
        neighboring signatures / type contracts.
        """
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as f:
            source_bytes = f.read()

        return self._slice_bytes(source_bytes, file_path, line_number)

    def slice_source(
        self, source_code: str, line_number: int, file_path: str = "snippet.ts"
    ) -> Optional[ASTSliceResult]:
        """Slices in-memory source string at the given 1-indexed line number."""
        source_bytes = source_code.encode("utf-8")
        return self._slice_bytes(source_bytes, file_path, line_number)

    def slice_function_by_name(self, file_path: str, function_name: str) -> Optional[ASTSliceResult]:
        """Finds a function, arrow function, or method by identifier name, preserving decorators."""
        if not os.path.exists(file_path):
            return None

        with open(file_path, "rb") as f:
            source_bytes = f.read()

        tree = self.parse_source(source_bytes, file_path)
        candidates = self._extract_candidates(tree.root_node)

        matching = [c for c in candidates if c.symbol_name == function_name]
        if not matching:
            return None

        chosen = matching[0]
        signatures = self._get_neighboring_signatures(tree.root_node, source_bytes, chosen, candidates)
        code_slice = source_bytes[chosen.start_byte : chosen.end_byte].decode("utf-8")

        return ASTSliceResult(
            file_path=file_path,
            symbol_name=chosen.symbol_name,
            symbol_type=chosen.symbol_type,
            start_line=chosen.start_row + 1,
            end_line=chosen.end_row + 1,
            code=code_slice,
            enclosing_class=chosen.enclosing_class_name,
            decorators=chosen.decorators,
            neighboring_signatures=signatures,
        )

    def _slice_bytes(self, source_bytes: bytes, file_path: str, line_number: int) -> Optional[ASTSliceResult]:
        tree = self.parse_source(source_bytes, file_path)
        target_row = max(0, line_number - 1)
        candidates = self._extract_candidates(tree.root_node)

        matching = [c for c in candidates if c.start_row <= target_row <= c.end_row]
        if not matching:
            return self._module_level_slice(file_path, source_bytes, target_row, tree.root_node)

        # Select innermost candidate (smallest span, latest start_row)
        chosen = min(matching, key=lambda c: (c.span, -c.start_row))
        signatures = self._get_neighboring_signatures(tree.root_node, source_bytes, chosen, candidates)
        code_slice = source_bytes[chosen.start_byte : chosen.end_byte].decode("utf-8")

        return ASTSliceResult(
            file_path=file_path,
            symbol_name=chosen.symbol_name,
            symbol_type=chosen.symbol_type,
            start_line=chosen.start_row + 1,
            end_line=chosen.end_row + 1,
            code=code_slice,
            enclosing_class=chosen.enclosing_class_name,
            decorators=chosen.decorators,
            neighboring_signatures=signatures,
        )

    def _extract_candidates(self, root_node: tree_sitter.Node) -> List[_Candidate]:
        candidates: List[_Candidate] = []

        def visit(node: tree_sitter.Node, current_class: Optional[Tuple[tree_sitter.Node, str]]):
            new_class = current_class
            if node.type in ("class_declaration", "abstract_class_declaration"):
                cname_node = node.child_by_field_name("name")
                cname = cname_node.text.decode("utf-8") if cname_node else "AnonymousClass"
                new_class = (node, cname)

            if node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                fname = name_node.text.decode("utf-8") if name_node else "anonymous"
                is_async = any(c.type == "async" for c in node.children)
                stype = "async_method" if is_async else "method"
                c_name = new_class[1] if new_class else None
                c_node = new_class[0] if new_class else None

                decs = self._get_preceding_decorators(node.parent, node) if node.parent else []
                s_byte = decs[0].start_byte if decs else node.start_byte
                e_byte = node.end_byte
                s_row = decs[0].start_point[0] if decs else node.start_point[0]
                e_row = node.end_point[0]
                dec_texts = [d.text.decode("utf-8") for d in decs]

                candidates.append(
                    _Candidate(
                        core_node=node,
                        slice_node=node,
                        symbol_name=fname,
                        symbol_type=stype,
                        start_byte=s_byte,
                        end_byte=e_byte,
                        start_row=s_row,
                        end_row=e_row,
                        enclosing_class_node=c_node,
                        enclosing_class_name=c_name,
                        decorators=dec_texts,
                    )
                )

            elif node.type in ("public_field_definition", "field_definition", "property_definition"):
                val = node.child_by_field_name("value")
                if val and val.type in ("arrow_function", "function_expression", "function"):
                    name_node = node.child_by_field_name("name")
                    fname = name_node.text.decode("utf-8") if name_node else "anonymous"
                    is_async = any(c.type == "async" for c in val.children)
                    stype = "async_method" if is_async else "method"
                    c_name = new_class[1] if new_class else None
                    c_node = new_class[0] if new_class else None

                    decs = self._get_preceding_decorators(node.parent, node) if node.parent else []
                    s_byte = decs[0].start_byte if decs else node.start_byte
                    e_byte = node.end_byte
                    s_row = decs[0].start_point[0] if decs else node.start_point[0]
                    e_row = node.end_point[0]
                    dec_texts = [d.text.decode("utf-8") for d in decs]

                    candidates.append(
                        _Candidate(
                            core_node=val,
                            slice_node=node,
                            symbol_name=fname,
                            symbol_type=stype,
                            start_byte=s_byte,
                            end_byte=e_byte,
                            start_row=s_row,
                            end_row=e_row,
                            enclosing_class_node=c_node,
                            enclosing_class_name=c_name,
                            decorators=dec_texts,
                        )
                    )

            elif node.type in ("function_declaration", "generator_function_declaration"):
                name_node = node.child_by_field_name("name")
                fname = name_node.text.decode("utf-8") if name_node else "anonymous"
                is_async = any(c.type == "async" for c in node.children)
                stype = "async_function" if is_async else "function"

                outer = node.parent if (node.parent and node.parent.type == "export_statement") else node
                decs = [c for c in node.children if c.type == "decorator"]
                dec_texts = [d.text.decode("utf-8") for d in decs]

                candidates.append(
                    _Candidate(
                        core_node=node,
                        slice_node=outer,
                        symbol_name=fname,
                        symbol_type=stype,
                        start_byte=outer.start_byte,
                        end_byte=outer.end_byte,
                        start_row=outer.start_point[0],
                        end_row=outer.end_point[0],
                        enclosing_class_node=None,
                        enclosing_class_name=None,
                        decorators=dec_texts,
                    )
                )

            elif node.type == "variable_declarator":
                val = node.child_by_field_name("value")
                if val and val.type in ("arrow_function", "function_expression", "function"):
                    name_node = node.child_by_field_name("name")
                    fname = name_node.text.decode("utf-8") if name_node else "anonymous"
                    is_async = any(c.type == "async" for c in val.children)
                    if val.type == "arrow_function":
                        stype = "async_arrow_function" if is_async else "arrow_function"
                    else:
                        stype = "async_function" if is_async else "function"

                    stmt = node.parent
                    if stmt:
                        # If variable statement has multiple declarators, slice only this declarator
                        decl_count = sum(1 for c in stmt.children if c.type == "variable_declarator")
                        if decl_count > 1:
                            outer = node
                        elif stmt.parent and stmt.parent.type == "export_statement":
                            outer = stmt.parent
                        else:
                            outer = stmt
                    else:
                        outer = node

                    candidates.append(
                        _Candidate(
                            core_node=val,
                            slice_node=outer,
                            symbol_name=fname,
                            symbol_type=stype,
                            start_byte=outer.start_byte,
                            end_byte=outer.end_byte,
                            start_row=outer.start_point[0],
                            end_row=outer.end_point[0],
                            enclosing_class_node=None,
                            enclosing_class_name=None,
                            decorators=[],
                        )
                    )

            elif node.type in ("arrow_function", "function_expression"):
                # Handle direct default export: export default () => { ... }
                if node.parent and node.parent.type == "export_statement":
                    is_async = any(c.type == "async" for c in node.children)
                    if node.type == "arrow_function":
                        stype = "async_arrow_function" if is_async else "arrow_function"
                    else:
                        stype = "async_function" if is_async else "function"

                    outer = node.parent
                    candidates.append(
                        _Candidate(
                            core_node=node,
                            slice_node=outer,
                            symbol_name="default",
                            symbol_type=stype,
                            start_byte=outer.start_byte,
                            end_byte=outer.end_byte,
                            start_row=outer.start_point[0],
                            end_row=outer.end_point[0],
                            enclosing_class_node=None,
                            enclosing_class_name=None,
                            decorators=[],
                        )
                    )

            for child in node.children:
                visit(child, new_class)

        visit(root_node, None)
        return candidates

    def _get_preceding_decorators(
        self, parent_node: tree_sitter.Node, child_node: tree_sitter.Node
    ) -> List[tree_sitter.Node]:
        """Finds any decorator siblings immediately preceding child_node in parent_node."""
        children = parent_node.children
        try:
            idx = children.index(child_node)
        except ValueError:
            return []

        decs: List[tree_sitter.Node] = []
        i = idx - 1
        while i >= 0:
            c = children[i]
            if c.type == "decorator":
                decs.insert(0, c)
            elif c.type == "comment":
                pass
            else:
                break
            i -= 1
        return decs

    def _get_neighboring_signatures(
        self,
        root_node: tree_sitter.Node,
        source_bytes: bytes,
        chosen: _Candidate,
        all_candidates: List[_Candidate],
    ) -> List[str]:
        signatures: List[str] = []

        # 1. If inside a class, extract other method signatures of that class
        if chosen.enclosing_class_node:
            class_sigs = self._extract_class_signatures(
                chosen.enclosing_class_node, source_bytes, exclude_func_name=chosen.symbol_name
            )
            signatures.extend(class_sigs)

        # 2. Extract interface definitions in the file
        interfaces = self._extract_interfaces(root_node)
        # Prioritize interfaces implemented by the class if applicable
        if chosen.enclosing_class_node:
            implemented = self._extract_implemented_interface_names(chosen.enclosing_class_node)
            if implemented:
                def iface_prio(text: str) -> int:
                    for name in implemented:
                        if name in text:
                            return 0
                    return 1
                interfaces.sort(key=iface_prio)
        signatures.extend(interfaces)

        # 3. Extract type alias contracts in the file
        type_aliases = self._extract_type_aliases(root_node)
        signatures.extend(type_aliases)

        # 4. If standalone function, include other top-level function signatures
        if not chosen.enclosing_class_node:
            for other in all_candidates:
                if not other.enclosing_class_node and other.symbol_name != chosen.symbol_name:
                    sig = self._extract_candidate_signature(other, source_bytes)
                    if sig and sig not in signatures:
                        signatures.append(sig)

        return signatures

    def _extract_class_signatures(
        self, class_node: tree_sitter.Node, source_bytes: bytes, exclude_func_name: str
    ) -> List[str]:
        signatures: List[str] = []
        body_node = class_node.child_by_field_name("body")
        if not body_node:
            return signatures

        for child in body_node.children:
            if child.type == "method_definition":
                name_node = child.child_by_field_name("name")
                fname = name_node.text.decode("utf-8") if name_node else ""
                if fname and fname != exclude_func_name:
                    mbody = child.child_by_field_name("body")
                    if mbody:
                        sig = source_bytes[child.start_byte : mbody.start_byte].decode("utf-8").strip()
                    else:
                        sig = child.text.decode("utf-8").strip()
                    if not sig.endswith(";"):
                        sig += ";"
                    signatures.append(sig)

            elif child.type in ("public_field_definition", "field_definition", "property_definition"):
                val = child.child_by_field_name("value")
                if val and val.type in ("arrow_function", "function_expression", "function"):
                    name_node = child.child_by_field_name("name")
                    fname = name_node.text.decode("utf-8") if name_node else ""
                    if fname and fname != exclude_func_name:
                        arrow_body = val.child_by_field_name("body")
                        if arrow_body:
                            sig = source_bytes[child.start_byte : arrow_body.start_byte].decode("utf-8").strip()
                        else:
                            sig = child.text.decode("utf-8").strip()
                        if not sig.endswith(";"):
                            sig += ";"
                        signatures.append(sig)

        return signatures

    def _extract_implemented_interface_names(self, class_node: tree_sitter.Node) -> List[str]:
        """Extracts interface names from an implements clause (e.g. class C implements I1, I2)."""
        implemented: List[str] = []
        for child in class_node.children:
            if child.type == "class_heritage":
                for hchild in child.children:
                    if hchild.type == "implements_clause":
                        for ichild in hchild.children:
                            if ichild.type in ("type_identifier", "identifier"):
                                implemented.append(ichild.text.decode("utf-8"))
        return implemented

    def _extract_interfaces(self, root_node: tree_sitter.Node) -> List[str]:
        """Extracts full interface declarations defined in the AST."""
        interfaces: List[str] = []

        def visit(node: tree_sitter.Node):
            if node.type == "interface_declaration":
                text = node.text.decode("utf-8")
                if text not in interfaces:
                    interfaces.append(text)
            for child in node.children:
                visit(child)

        visit(root_node)
        return interfaces

    def _extract_type_aliases(self, root_node: tree_sitter.Node) -> List[str]:
        """Extracts type alias definitions defined in the AST."""
        type_aliases: List[str] = []

        def visit(node: tree_sitter.Node):
            if node.type == "type_alias_declaration":
                text = node.text.decode("utf-8")
                if text not in type_aliases:
                    type_aliases.append(text)
            for child in node.children:
                visit(child)

        visit(root_node)
        return type_aliases

    def _extract_candidate_signature(self, candidate: _Candidate, source_bytes: bytes) -> str:
        """Extracts a concise signature string from a standalone candidate."""
        node = candidate.core_node
        body = node.child_by_field_name("body")
        if body:
            sig = source_bytes[candidate.start_byte : body.start_byte].decode("utf-8").strip()
        else:
            sig = source_bytes[candidate.start_byte : candidate.end_byte].decode("utf-8").strip()
        if not sig.endswith(";"):
            sig += ";"
        return sig

    def _module_level_slice(
        self,
        file_path: str,
        source_bytes: bytes,
        target_row: int,
        root_node: Optional[tree_sitter.Node] = None,
    ) -> ASTSliceResult:
        """Fallback slice when target_row is outside any function or method (e.g. imports, comments)."""
        lines = source_bytes.decode("utf-8", errors="replace").splitlines()
        start = max(0, target_row - 10)
        end = min(len(lines), target_row + 11)
        code = "\n".join(lines[start:end])

        signatures: List[str] = []
        if root_node:
            signatures.extend(self._extract_interfaces(root_node))
            signatures.extend(self._extract_type_aliases(root_node))

        return ASTSliceResult(
            file_path=file_path,
            symbol_name="<module>",
            symbol_type="module_level",
            start_line=start + 1,
            end_line=end,
            code=code,
            enclosing_class=None,
            decorators=[],
            neighboring_signatures=signatures,
        )
