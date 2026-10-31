import os
import tempfile
import pytest
from autoheal.parsers.ts_slicer import TypeScriptASTSlicer, ASTSliceResult

SAMPLE_TS = """// Top-level module comment
import { useState } from 'react';

export interface ICalculator {
  add(a: number, b: number): number;
  divide(a: number, b: number): number;
}

export type OperationResult = {
  value: number;
  error?: string;
};

export class Calculator implements ICalculator {
  @log
  add(a: number, b: number): number {
    return a + b;
  }

  divide(a: number, b: number): number {
    if (b === 0) {
      throw new Error("division by zero");
    }
    return a / b;
  }
}

export function standaloneAdd(a: number, b: number): number {
  const sum = a + b;
  return sum;
}

export const multiply = (a: number, b: number): number => {
  const result = a * b;
  return result;
};

export async function fetchRemoteData(url: string): Promise<OperationResult> {
  const response = await fetch(url);
  const data = await response.json();
  return { value: data.value };
}
"""


def test_ast_slice_standalone_function():
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_TS)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        # Line 29 is 'const sum = a + b;' inside standaloneAdd
        result = slicer.slice_at_line(temp_path, 29)
        assert result is not None
        assert result.symbol_name == "standaloneAdd"
        assert result.symbol_type == "function"
        assert result.enclosing_class is None
        assert "function standaloneAdd(a: number, b: number): number" in result.code
        assert "return sum;" in result.code
        assert result.start_line <= 28
        assert result.end_line >= 31
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_arrow_function():
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_TS)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        # Line 34 is 'const result = a * b;' inside multiply
        result = slicer.slice_at_line(temp_path, 34)
        assert result is not None
        assert result.symbol_name == "multiply"
        assert result.symbol_type in ("arrow_function", "function")
        assert result.enclosing_class is None
        assert "multiply = (a: number, b: number): number =>" in result.code
        assert "return result;" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_class_method_with_interface():
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_TS)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        # Line 23 is 'return a / b;' inside Calculator.divide
        result = slicer.slice_at_line(temp_path, 23)
        assert result is not None
        assert result.symbol_name == "divide"
        assert result.symbol_type == "method"
        assert result.enclosing_class == "Calculator"
        assert "divide(a: number, b: number): number" in result.code
        assert 'throw new Error("division by zero");' in result.code

        # Neighboring signatures must capture class method and interface contract
        assert len(result.neighboring_signatures) >= 2
        assert any("add" in s for s in result.neighboring_signatures)
        assert any("ICalculator" in s for s in result.neighboring_signatures)
        assert any("OperationResult" in s for s in result.neighboring_signatures)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_async_function():
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_TS)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        # Line 40 is 'const response = await fetch(url);' inside fetchRemoteData
        result = slicer.slice_at_line(temp_path, 40)
        assert result is not None
        assert result.symbol_name == "fetchRemoteData"
        assert result.symbol_type == "async_function"
        assert result.enclosing_class is None
        assert "async function fetchRemoteData" in result.code
        assert "await fetch(url)" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_async_arrow_function():
    code = """const asyncCompute = async (x: number): Promise<number> => {
  const result = await Promise.resolve(x * 10);
  return result;
};
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        result = slicer.slice_at_line(temp_path, 2)
        assert result is not None
        assert result.symbol_name == "asyncCompute"
        assert result.symbol_type == "async_arrow_function"
        assert "const asyncCompute = async" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_method_with_decorators():
    code = """class UserService {
  @Authorized('admin')
  @AuditLog('delete_user')
  async deleteUser(userId: string): Promise<boolean> {
    return true;
  }
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        result = slicer.slice_at_line(temp_path, 4)
        assert result is not None
        assert result.symbol_name == "deleteUser"
        assert result.symbol_type == "async_method"
        assert result.enclosing_class == "UserService"
        assert "@Authorized('admin')" in result.decorators
        assert "@AuditLog('delete_user')" in result.decorators
        assert "@Authorized('admin')" in result.code
        assert result.start_line == 2
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_tsx_react_component():
    tsx_code = """import React from 'react';

interface ButtonProps {
  label: string;
  onClick: () => void;
}

export const ActionButton: React.FC<ButtonProps> = ({ label, onClick }) => {
  return (
    <button className="btn" onClick={onClick}>
      <span>{label}</span>
    </button>
  );
};
"""
    with tempfile.NamedTemporaryFile("w", suffix=".tsx", delete=False, encoding="utf-8") as f:
        f.write(tsx_code)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        result = slicer.slice_at_line(temp_path, 10)
        assert result is not None
        assert result.symbol_name == "ActionButton"
        assert "<button className=\"btn\"" in result.code
        assert "<span>{label}</span>" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_javascript_js():
    js_code = """// Plain JS
function calculateTax(subtotal, rate) {
  const tax = subtotal * rate;
  return tax;
}

const formatCurrency = (amount) => {
  return `$${amount.toFixed(2)}`;
};
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js_code)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        result_fn = slicer.slice_at_line(temp_path, 3)
        assert result_fn is not None
        assert result_fn.symbol_name == "calculateTax"
        assert result_fn.symbol_type == "function"

        result_arrow = slicer.slice_at_line(temp_path, 8)
        assert result_arrow is not None
        assert result_arrow.symbol_name == "formatCurrency"
        assert result_arrow.symbol_type == "arrow_function"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_slice_function_by_name():
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_TS)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        # Find standalone function
        res_fn = slicer.slice_function_by_name(temp_path, "standaloneAdd")
        assert res_fn is not None
        assert res_fn.symbol_name == "standaloneAdd"
        assert res_fn.symbol_type == "function"

        # Find arrow function
        res_arrow = slicer.slice_function_by_name(temp_path, "multiply")
        assert res_arrow is not None
        assert res_arrow.symbol_name == "multiply"

        # Find class method
        res_method = slicer.slice_function_by_name(temp_path, "divide")
        assert res_method is not None
        assert res_method.symbol_name == "divide"
        assert res_method.enclosing_class == "Calculator"

        # Find non-existent
        assert slicer.slice_function_by_name(temp_path, "missingFunction") is None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_module_level():
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_TS)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        # Line 1 is top-level comment
        result = slicer.slice_at_line(temp_path, 1)
        assert result is not None
        assert result.symbol_name == "<module>"
        assert result.symbol_type == "module_level"
        assert result.enclosing_class is None
        assert any("ICalculator" in s for s in result.neighboring_signatures)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_nested_function():
    code = """function outerFunction(x: number) {
  function innerHelper(y: number) {
    return y * 2;
  }
  return innerHelper(x) + 5;
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        slicer = TypeScriptASTSlicer()
        # Line 3 is inside innerHelper
        result = slicer.slice_at_line(temp_path, 3)
        assert result is not None
        assert result.symbol_name == "innerHelper"
        assert "function innerHelper(y: number)" in result.code
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ast_slice_nonexistent_file():
    slicer = TypeScriptASTSlicer()
    assert slicer.slice_at_line("non_existent_file_xyz_123.ts", 10) is None
    assert slicer.slice_function_by_name("non_existent_file_xyz_123.ts", "anyFunc") is None


def test_slice_source_in_memory():
    slicer = TypeScriptASTSlicer()
    code = """function compute(a: number, b: number): number {
  return a ** b;
}"""
    result = slicer.slice_source(code, 2)
    assert result is not None
    assert result.symbol_name == "compute"
    assert "return a ** b;" in result.code
