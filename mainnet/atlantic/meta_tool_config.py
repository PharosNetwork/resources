#!/usr/bin/env python3
import json
import subprocess
import argparse
import os
import sys
from typing import Any, Dict, Optional, Union
from pathlib import Path

class ConfigManager:
    def __init__(self, tool_path: str = "./meta_tool", tool_args: list = None, working_dir: str = None):
        self.tool_path = tool_path
        self.tool_args = tool_args or []
        self.working_dir = working_dir

    def _run_tool(self, args: list) -> subprocess.CompletedProcess:
        full_args = [self.tool_path] + self.tool_args + args
        try:
            return subprocess.run(
                full_args,
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Tool execution failed: {e.stderr or str(e)}")

    def _get_nested(self, d: Dict[str, Any], path: str) -> Optional[Any]:
        keys = path.split(".")
        current = d
        for key in keys:
            if key not in current:
                return None
            current = current[key]
        return current

    def _set_nested(self, d: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
        keys = path.split('.')
        current = d
        modified = False
    
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
                modified = True
            current = current[key]
    
        last_key = keys[-1]
        if last_key not in current or current[last_key] != value:
            current[last_key] = value
            modified = True
    
        return modified

    def get_from_tool(self, key: str) -> Dict[str, Any]:
        try:
            result = self._run_tool(["-get", f"-key={key}"])
            lines = result.stdout.splitlines()
            if len(lines) < 3:
                raise ValueError("Unexpected output format from tool")
            return json.loads(lines[2])
        except (ValueError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to parse tool output for key {key}: {str(e)}")

    def get_from_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to get config from file {file_path}: {str(e)}")

    def modify_config(
        self,
        config: Dict[str, Any],
        jq_path: str,
        expected_value: Any,
        
    ) -> Dict[str, Any]:
        return self._set_nested(config, jq_path, expected_value)

    def set_to_tool(self, key: str, value: Dict[str, Any]) -> bool:
        try:
            json_str = json.dumps(value)
            result = self._run_tool(["-set", f"-key={key}", f"-value={json_str}"])
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to set config to tool for key {key}: {str(e)}")

    def set_to_file(self, file_path: Union[str, Path], value: Dict[str, Any]) -> bool:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(value, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, TypeError) as e:
            raise RuntimeError(f"Failed to set config to file {file_path}: {str(e)}")

    def _parse_value(self, value_str: str) -> Any:
        if value_str.lower() in ('true', 'false'):
            return value_str
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            return value_str

    def update_via_tool(
        self,
        key: str,
        jq_path: str,
        value_str: Any,
    ) -> bool:
        try:
            converted_value = self._parse_value(value_str)
            current_config = self.get_from_tool(key)
            if not self.modify_config(current_config, jq_path, converted_value):
                return False
            return self.set_to_tool(key, current_config)
        except Exception as e:
            raise RuntimeError(f"Tool-based update failed for key {key}: {str(e)}")

    def update_via_file(
        self,
        file_path: Union[str, Path],
        jq_path: str,
        value_str: Any,
    ) -> bool:
        try:
            converted_value = self._parse_value(value_str)
            current_config = self.get_from_file(file_path)
            if not self.modify_config(current_config, jq_path, converted_value):
                return False
            return self.set_to_file(file_path, current_config)
        except Exception as e:
            raise RuntimeError(f"File-based update failed for {file_path}: {str(e)}")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Configuration Management Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--tool", action="store_true", help="Use tool-based configuration")
    mode_group.add_argument("--file", action="store_true", help="Use file-based configuration")
    
    parser.add_argument("--key", help="Configuration key (required for tool mode)")
    parser.add_argument("--path", help="JSON path to modify (e.g. 'a.b.c')", required=True)
    parser.add_argument("--value", help="Value to set (use 'true'/'false' to keep as string)", required=True)
    parser.add_argument("--file-path", help="Configuration file path (required for file mode)")
    
    tool_group = parser.add_argument_group("Tool options")
    tool_group.add_argument("--tool-path", default="./meta_tool", help="Path to configuration tool")
    tool_group.add_argument("--tool-conf", default="./meta_service.conf", help="Tool configuration file path (e.g. './conf.json')")
    tool_group.add_argument("--tool-arg", action="append", help="Additional tool arguments (can specify multiple)")
    tool_group.add_argument("--working-dir", default="/data/pharos-node/domain/client/bin", help="Working directory to run the tool in")
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    tool_args = []
    if args.tool_conf:
        tool_args.extend(["-conf", args.tool_conf])
    if args.tool_arg:
        tool_args.extend(args.tool_arg)
    
    manager = ConfigManager(
        tool_path=args.tool_path,
        tool_args=tool_args,
        working_dir=args.working_dir
    )
    
    try:
        if args.tool:
            if not args.key:
                raise ValueError("--key is required in tool mode")
            updated = manager.update_via_tool(
                args.key,
                args.path,
                args.value,
            )
            print(f"Tool config {'updated' if updated else 'unchanged'}")
        elif args.file:
            if not args.file_path:
                raise ValueError("--file-path is required in file mode")
            updated = manager.update_via_file(
                args.file_path,
                args.path,
                args.value,
            )
            print(f"File config {'updated' if updated else 'unchanged'}")
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
