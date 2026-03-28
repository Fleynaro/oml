import xml.etree.ElementTree as ET
import re
from types import SimpleNamespace
from typing import Optional, Dict, Any, List, Callable, Tuple
from enum import Enum, auto
from dataclasses import dataclass

class Tag(str, Enum):
    OML = "oml"
    PACKAGE = "Package"
    COMPONENT = "Component"
    INPUT = "Input"
    LOCAL = "Local"
    SET = "Set"
    OUTPUT = "Output"
    IF = "If"
    ELSE = "Else"
    REPEAT = "Repeat"
    CALL = "Call"
    POST_EXECUTE = "PostExecute"
    ASSERT = "Assert"
    DEBUG_PRINT = "DebugPrint"
    TEST_PRINT = "TestPrint"

class Attr(str, Enum):
    NAME = "name"
    TYPE = "type"
    CONTEXT = "context"
    CHILDREN = "children"
    SET = "set"
    DEFAULT = "default"
    CONDITION = "condition"
    WHILE = "while"
    FROM = "from"
    TO = "to"
    STEP = "step"
    PARAMS = "params"
    RETURN = "return"
    TEXT = "text"
    EXTEND = "extend"
    OUTPUT = "output"

class DataType(str, Enum):
    UNKNOWN = "unknown"
    ANY = "any"
    COMPONENT = "component"
    STRUCT = "struct"
    BOOL = "bool"
    FLOAT = "float"
    INT = "int"
    STR = "str"

class FunctionCallResult:
    def __init__(self, function_name: str, result: Any) -> None:
        self.function_name = function_name
        self.result = result

    def __repr__(self) -> str:
        return f"FunctionCallResult({self.function_name}, {self.result})"

class ComponentCallResult:
    def __init__(self, component_path: str, outputs: Any) -> None:
        self.component_path = component_path
        self.outputs = outputs

    def __repr__(self) -> str:
        return f"ComponentCallResult({self.component_path}, {self.outputs})"

class VarType(Enum):
    INPUT = auto()
    LOCAL = auto()
    OUTPUT = auto()
    OUTPUT_CONTEXT = auto()

@dataclass
class Variable:
    """Container for value and its scope metadata."""
    value: Any
    var_type: VarType

@dataclass
class Children:
    """Container for children metadata."""
    input: bool = False

class Scope:
    """Stores variables of the current frame and a reference to the parent scope."""
    
    def __init__(
        self, 
        parent: Optional['Scope'] = None, 
        name: str = "anonymous", 
        component_path: Optional[str] = None, 
        call_node: Optional[ET.Element] = None, 
        init_outputs: Dict[str, Any] = None
    ) -> None:
        self.parent = parent
        self.name = name
        self.component_path = component_path
        self.call_node = call_node
        
        # Unified storage: mapping name -> Variable object
        self.variables: Dict[str, Variable] = {}
        
        # Initialize outputs if provided
        if init_outputs:
            for k, v in init_outputs.items():
                self.variables[k] = Variable(value=v, var_type=VarType.OUTPUT)
                
        self.post_exec_nodes: List[Tuple[ET.Element, Scope]] = []
        self.calls: List[Any] = []
        self.children = Children()

    def get_variables(self):
        return self.variables

    def add_call(self, call: Any) -> None:
        self.calls.append(call)

    def add_post_exec_node(self, node: ET.Element, scope: 'Scope') -> None:
        self.post_exec_nodes.append((node, scope))

    def _set_by_path(self, variables: Dict[str, Variable], path: str, value: Any, var_type: VarType) -> None:
        """
        Handles deep writes. If the root key doesn't exist in the target scope, 
        it creates a new Variable entry.
        """
        if not path:
            items_to_add = {}
            if isinstance(value, dict):
                items_to_add = value
            elif isinstance(value, SimpleNamespace):
                items_to_add = vars(value)
            
            # Wrap each value into a Variable object before updating the storage
            for k, v in items_to_add.items():
                # If the value is a dict, we still want to convert it to SimpleNamespace 
                # for dot-access consistency as seen in the rest of the logic.
                final_val = SimpleNamespace(**v) if isinstance(v, dict) and not isinstance(v, SimpleNamespace) else v
                variables[k] = Variable(value=final_val, var_type=var_type)
            return

        parts = path.split('.')
        root_key = parts[0]
        if not all(part.isidentifier() for part in parts if part):
            raise NameError(f"Invalid variable path: '{path}'. Each part must be a valid Python identifier.")

        # Convert dict to SimpleNamespace for nested access consistency
        if isinstance(value, dict):
            value = SimpleNamespace(**value)

        # 1. Ensure the root Variable exists in this specific scope instance
        if root_key not in variables:
            # If we are setting a deep path but the root is missing, 
            # we initialize the root based on the provided var_type.
            initial_val = SimpleNamespace() if len(parts) > 1 else value
            variables[root_key] = Variable(value=initial_val, var_type=var_type)
        
        target_var = variables[root_key]
        
        # 2. If it's a simple flat set (no dots)
        if len(parts) == 1:
            target_var.value = value
            if target_var.var_type != VarType.OUTPUT:
                target_var.var_type = var_type # Update type if it changed
            return

        # 3. Handle nested path (dots)
        current = target_var.value
        for part in parts[1:-1]:
            # Navigate or create SimpleNamespace
            next_node = getattr(current, part, None) if isinstance(current, SimpleNamespace) else current.get(part)
            if not isinstance(next_node, (dict, SimpleNamespace)):
                next_node = SimpleNamespace()
                if isinstance(current, dict):
                    current[part] = next_node
                else:
                    setattr(current, part, next_node)
            current = next_node

        # Set the final leaf value
        last_part = parts[-1]
        if isinstance(current, dict):
            current[last_part] = value
        else:
            setattr(current, last_part, value)

    def _find_owner_scope(self, path: str) -> 'Scope':
        """
        Climbs up the hierarchy to find which scope actually 'owns' the root of this path.
        Returns 'self' if not found anywhere (new variable creation).
        """
        root = path.split('.')[0]
        current = self
        while current is not None:
            if root in current.get_variables():
                return current
            current = current.parent
        return self

    def set_variable(self, path: str, value: Any, var_type = VarType.LOCAL) -> None:
        owner = self._find_owner_scope(path)
        self._set_by_path(owner.variables, path, value, var_type)

    def get(self, path: str, default: Any = None) -> Any:
        parts = path.split('.')
        # Use as_dict() logic to respect scope inheritance for retrieval
        current_data = self.as_dict()
        try:
            current = current_data
            for part in parts:
                if isinstance(current, dict):
                    current = current[part]
                else:
                    current = getattr(current, part)
            return current
        except (AttributeError, KeyError, TypeError):
            return default

    def as_dict(self) -> Dict[str, Any]:
        """
        Flattens the scope hierarchy into a single dict of raw values for eval().
        Parent variables are overwritten by child variables (standard shadowing).
        """
        result_dict: Dict[str, Any] = {}
        
        # 1. Recursively get data from parent
        if self.parent:
            result_dict.update(self.parent.as_dict())
        
        # 2. Inject scope metadata
        result_dict["__scope__"] = SimpleNamespace(
            parent=result_dict.get("__scope__"),
            name=self.name,
            component_path=self.component_path,
            calls=self.calls
        )
        
        # 3. Update with current variables (extracting .value from the Variable object)
        # Note: We don't filter by type here to maintain existing 'shadowing' logic
        for name, var_obj in self.get_variables().items():
            result_dict[name] = var_obj.value
            
        return result_dict

class UnionScope(Scope):
    """
    A Scope that is a union of two other scopes.
    """
    def __init__(self, target_scope: Scope, caller_scope: Scope, var_types = None) -> None:
        # copy all attributes of caller_scope
        self.__dict__.update(caller_scope.__dict__)
        self.target = target_scope 
        self.caller = caller_scope
        self.parent = caller_scope
        self.var_types = var_types

    def get_variables(self):
        variables = self.variables.copy()
        variables.update({
            k: v for k, v in self.target.variables.items() 
            if self.var_types is None or v.var_type in self.var_types
        })
        return variables

class ComponentValue:
    """Stores the component implementation passed as an argument."""
    def __init__(self, component_path: str, impl_node: ET.Element, decl_node: ET.Element, decl_scope: Scope) -> None:
        self.component_path = component_path
        self.impl_node = impl_node
        self.decl_node = decl_node
        self.decl_scope = decl_scope # Scope where this component was defined (caller)

# --- Interpreter ---
class OMLInterpreter:
    def __init__(self, custom_data_types: Dict[str, Any] = {}, system_functions: Dict[str, Callable] = {}, strict_xml=False) -> None:
        self.global_scope = Scope(name="global")
        self.system_functions = system_functions
        self.strict_xml = strict_xml
        self.testPrint = ""
        self.data_types = {
            DataType.UNKNOWN: None,
            DataType.ANY: None,
            DataType.COMPONENT: None,
            DataType.STRUCT: None,
            DataType.BOOL: bool,
            DataType.FLOAT: float,
            DataType.INT: int,
            DataType.STR: str
        }
        self.data_types.update(custom_data_types)

    def _eval_expr(self, expr_str: str, scope: Scope, throw=False) -> Any:
        """Evaluates a Python expression in the current context."""
        if not isinstance(expr_str, str):
            return expr_str
        # base
        context = scope.as_dict()

        # custom types
        context['SimpleNamespace'] = SimpleNamespace
        context.update(self.data_types)

        # custom functions
        default_calls: List[ComponentCallResult | FunctionCallResult] = context.get('__calls__', scope.calls)
        context['calls'] = lambda calls = default_calls: [(call.outputs if isinstance(call, ComponentCallResult) else call.result) for call in calls]
        context['component_calls'] = lambda calls = default_calls: [call.outputs for call in calls if isinstance(call, ComponentCallResult)]
        context['function_calls'] = lambda calls = default_calls: [call.result for call in calls if isinstance(call, FunctionCallResult)]

        try:
            # Limited eval with access to scope variables
            return eval(expr_str, {}, context)
        except Exception as e:
            if throw:
                raise e
            # If it couldn't be evaluated as an expression, return as a None
            return None
        
    def _cast(self, value, to_data_type):
        if isinstance(value, to_data_type):
            return value
        if to_data_type == bool and isinstance(value, str):
            return value.lower() not in ["false", "0"]
        try:
            return to_data_type(value)
        except (ValueError, TypeError):
            raise TypeError(f"Cannot cast value '{value}' (type {type(value).__name__}) to {to_data_type.__name__}")

    def _eval_attr(self, text: str, scope: Scope, cast=None, wrap="<expr>") -> Any:
        result = None
        if text.startswith("{") and text.endswith("}"):
            result = self._eval_expr(wrap.replace("<expr>", text[1:-1]), scope)
        else:
            if not text: return ""
            def replace(match: re.Match) -> str:
                expr = match.group(1)
                result = self._eval_expr(expr, scope)
                return str(result)
            result = re.sub(r'\{(.*?)\}', replace, text)
        if cast:
            result = self._cast(result, cast)
        return result

    def _process_var_recursive(self, node: ET.Element, scope: Scope, var_type: VarType, prefix: str = "", caller_scope: Scope = None) -> None:
        tag = node.tag
        name = self._eval_attr(node.attrib.get(Attr.NAME, ""), scope, cast=str)
        type = DataType.COMPONENT if tag == Tag.COMPONENT else self._eval_attr(node.attrib.get(Attr.TYPE, DataType.UNKNOWN), scope, cast=str)
        is_context = self._eval_attr(node.attrib.get(Attr.CONTEXT, "false"), scope, cast=bool)

        if type not in self.data_types:
            raise Exception(f"Unsupported type '{type}' for variable '{name}' in the scope '{scope.name}'")
        data_type = self.data_types[type]
        
        # Form the full path using a dot
        full_path = f"{prefix}.{name}" if prefix and name else (name or prefix)
        val = scope.get(full_path)
        
        # Value Resolution Logic
        if type == DataType.STRUCT and (val is None or is_context):
            val = {}
        elif type == DataType.COMPONENT and val is None:
            if caller_scope is None:
                raise Exception(f"Cannot use component input '{name}' in the scope '{scope.name}'")
            children = self._eval_attr(node.attrib.get(Attr.CHILDREN, "false"), scope, cast=bool)
            full_comp_path = f"{scope.component_path}.{full_path}"
            implementation_node = (scope.call_node if children else scope.call_node.find(name)) if tag == Tag.INPUT else None
            decl_scope = caller_scope
            if implementation_node is None:
                implementation_node = node
                decl_scope = scope
            val = ComponentValue(full_comp_path, implementation_node, node, decl_scope)
            if children:
                scope.children.input = True
        elif Attr.SET in node.attrib:
            val = self._eval_attr(node.attrib.get(Attr.SET), scope, cast=data_type)
        elif tag == Tag.INPUT and val is None:
            # Specific logic for Input: look for a default if no value exists
            if Attr.DEFAULT not in node.attrib:
                raise ValueError(f"Input '{name}' not found in scope '{scope.name}' ({scope.component_path})")
            val = self._eval_attr(node.attrib.get(Attr.DEFAULT), scope, cast=data_type)

        if is_context:
            if tag not in [Tag.INPUT, Tag.OUTPUT]:
                raise ValueError(f"Unsupported context type '{tag}' for variable '{full_path}' in component '{scope.component_path}'")
            if "." in full_path:
                raise ValueError(f"Only root variables can be context variables. Variable '{full_path}' in component '{scope.component_path}' is not allowed.")
            if tag == Tag.OUTPUT:
                var_type = VarType.OUTPUT_CONTEXT

        # Set value (if defined)
        if val is not None:
            # Cast value to the specified type
            if data_type is not None:
                val = self._cast(val, data_type)
            scope.set_variable(full_path, val, var_type)

        # Recursion over child elements of the same type
        if type != DataType.COMPONENT:
            for child in node:
                if child.tag not in [tag, Tag.COMPONENT]:
                    raise Exception(f"Unsupported child type '{child.tag}' for variable '{name}' in the scope '{scope.name}'")
                self._process_var_recursive(child, scope, var_type, prefix=full_path, caller_scope=caller_scope)

    def _execute_node(self, node: ET.Element, scope: Scope, caller_scope: Optional[Scope] = None) -> None:
        """Recursive traversal and execution of nodes."""
        tag = node.tag

        if tag in [Tag.OML, Tag.PACKAGE]:
            # Ignore meta-tags, just go deeper
            for child in node:
                self._execute_node(child, scope)

        elif tag == Tag.COMPONENT:
            comp_name = self._eval_attr(node.attrib.get(Attr.NAME), scope, cast=str)
            output = self._eval_attr(node.attrib.get(Attr.OUTPUT, "false"), scope, cast=bool)
            if len(comp_name) == 0:
                raise ValueError(f"Invalid component name '{comp_name}' in the scope '{scope.name}'")
            # Define full name: if we are inside another component, add a prefix
            # scope.component_path stores the path (e.g., "Path")
            full_path = f"{scope.component_path}.{comp_name}" if scope.component_path else comp_name
            scope.set_variable(comp_name, ComponentValue(full_path, node, node, scope), VarType.OUTPUT if output else VarType.LOCAL)

        elif tag == Tag.INPUT:
            self._process_var_recursive(node, scope, VarType.INPUT, caller_scope=caller_scope)

        elif tag == Tag.LOCAL or tag == Tag.SET:
            self._process_var_recursive(node, scope, VarType.LOCAL, caller_scope=caller_scope)

        elif tag == Tag.OUTPUT:
            self._process_var_recursive(node, scope, VarType.OUTPUT, caller_scope=caller_scope)

        # --- Conditions (If / Else) ---
        elif tag == Tag.IF:
            is_true = self._eval_attr(node.attrib.get(Attr.CONDITION, "false"), scope, cast=bool)

            if is_true:
                # If True - execute all tags EXCEPT <Else>
                for child in node:
                    if child.tag != Tag.ELSE:
                        self._execute_node(child, scope)
            else:
                # If False - find the <Else> tag and execute its content
                for child in node:
                    if child.tag == Tag.ELSE:
                        for else_child in child:
                            self._execute_node(else_child, scope)

        # --- Loops (Repeat) ---
        elif tag == Tag.REPEAT:
            loop_var = self._eval_attr(node.attrib.get(Attr.NAME, "i"), scope, cast=str)

            if "while" in node.attrib:
                # Execute while condition is True
                while self._eval_attr(node.attrib.get(Attr.WHILE), scope, cast=bool):
                    for child in node:
                        self._execute_node(child, scope)
            else:
                # From-to-step loop
                try:
                    start_val = self._eval_attr(node.attrib.get(Attr.FROM, "0"), scope, cast=float)
                    end_val = self._eval_attr(node.attrib.get(Attr.TO, "0"), scope, cast=float)
                    step_val = self._eval_attr(node.attrib.get(Attr.STEP, "1"), scope, cast=float)
                except ValueError:
                    start_val, end_val, step_val = 0.0, 0.0, 1.0

                current_val = start_val
                
                # Function for safe boundary check (considering floating point and step sign)
                def check_bounds(curr: float, end: float, step: float) -> bool:
                    if step > 0: return curr <= end + 1e-9
                    else: return curr >= end - 1e-9

                while check_bounds(current_val, end_val, step_val):
                    # Store iterator in local scope so it's accessible inside the loop
                    # If the number is an integer, cast to int for aesthetics
                    scope.set_variable(loop_var, int(current_val) if current_val.is_integer() else current_val)
                    
                    for child in node:
                        self._execute_node(child, scope)
                        
                    current_val += step_val

        elif tag == Tag.CALL:
            # Python system function call
            func_name = self._eval_attr(node.attrib.get(Attr.NAME), scope, cast=str)
            params = self._eval_attr(node.attrib.get(Attr.PARAMS, "{}"), scope, wrap="SimpleNamespace(<expr>)")
            ret_var = self._eval_attr(node.attrib.get(Attr.RETURN, ""), scope, cast=str)

            if func_name in self.system_functions:
                result = self.system_functions[func_name](**vars(params))
                scope.add_call(FunctionCallResult(func_name, result))
                if len(ret_var) > 0:
                    scope.set_variable(ret_var, result)
            else:
                raise ValueError(f"System function '{func_name}' not found.")

        elif tag == Tag.POST_EXECUTE:
            # Just save node to the current scope's queue
            scope.add_post_exec_node(node, scope)

        elif tag == Tag.ASSERT:
            if Attr.CONDITION not in node.attrib:
                raise ValueError("Assert node must have a 'condition' attribute.")
            condition = self._eval_attr(node.attrib.get(Attr.CONDITION, "false"), scope, cast=bool)
            text = self._eval_attr(node.attrib.get(Attr.TEXT, ""), scope, cast=str)
            if not condition:
                raise Exception(text) if text else Exception(f"Assertion failed: {node.attrib.get(Attr.CONDITION, 'false')} is false in '{scope.component_path}'")

        elif tag == Tag.DEBUG_PRINT:
            text = self._eval_attr(node.attrib.get(Attr.TEXT, ""), scope, cast=str)
            print(f"[Debug] {text}")
        
        elif tag == Tag.TEST_PRINT:
            text = self._eval_attr(node.attrib.get(Attr.TEXT, ""), scope, cast=str)
            self.testPrint += f"{text}\n"

        else:
            # If tag is not built-in, it's a custom component call
            self.call_component(tag, node, scope)

    def _find_component(self, component_path: str, scope: Scope) -> Optional[Tuple[Optional[ET.Element], Scope, Optional[str], str, dict[str, Any]]]:
        # 1. Get the component value
        val = scope.get(component_path)
        if isinstance(val, SimpleNamespace):
            comp_def = None
            decl_scope = scope
            extend_name = ""
            full_path = ""
            init_outputs = vars(val)
            return (comp_def, decl_scope, extend_name, full_path, init_outputs)
        if isinstance(val, ComponentValue):
            comp_def = val.impl_node
            decl_scope = val.decl_scope
            extend_name = self._eval_attr(val.decl_node.attrib.get(Attr.EXTEND, ""), decl_scope, cast=str)
            full_path = val.component_path
            return (comp_def, decl_scope, extend_name, full_path, {})
        return None

    def call_component(self, comp_name: str, call_node: ET.Element, caller_scope: Scope) -> None:
        # Attempt to find the component
        found = self._find_component(comp_name, caller_scope)
        if not found:
            raise Exception(f"Component '{comp_name}' not found. Try to check accessibility.")
        comp_def, decl_scope, extend_name, full_path, init_outputs = found

        # Unified execution logic
        instance_name = self._eval_attr(call_node.attrib.get(Attr.NAME, f"anon_{comp_name}"), caller_scope, cast=str)
        new_scope = Scope(
            parent=decl_scope,
            name=instance_name,
            component_path=full_path,
            call_node=call_node,
            init_outputs=init_outputs
        )

        if comp_def is not None:
            # Context propagation
            for name, var in caller_scope.get_variables().items():
                if var.var_type == VarType.OUTPUT_CONTEXT:
                    new_scope.set_variable(name, var.value, VarType.OUTPUT_CONTEXT)

            # Pass attributes (Inputs)
            for attr_name, attr_val in call_node.attrib.items():
                new_scope.set_variable(attr_name, self._eval_attr(attr_val, caller_scope), VarType.INPUT)

            # Handle inheritance (base code)
            if extend_name:
                self._handle_extend(extend_name, new_scope, caller_scope=caller_scope)

            # Execute main body
            for child in comp_def:
                self._execute_node(child, new_scope, caller_scope=caller_scope)

            # Execute PostExecute (if any)
            for post_node, scope in new_scope.post_exec_nodes:
                for child in post_node:
                    self._execute_node(child, scope, caller_scope=caller_scope)

            # Return calls
            new_scope.set_variable("__calls__", new_scope.calls, VarType.OUTPUT)

            # Results to caller scope
            outputs = SimpleNamespace(**{
                name: var.value 
                for name, var in new_scope.get_variables().items() 
                if var.var_type in [VarType.OUTPUT, VarType.OUTPUT_CONTEXT]
            })
            caller_scope.add_call(ComponentCallResult(full_path, outputs))
            if Attr.NAME in call_node.attrib:
                caller_scope.set_variable(instance_name, outputs)

        # Execute child tags of the CALL
        # They see: component's Outputs + caller's Scope (caller_scope)
        if not new_scope.children.input:
            union_scope = UnionScope(new_scope, caller_scope, var_types=[VarType.OUTPUT, VarType.OUTPUT_CONTEXT])
            for child in call_node:
                if child.tag in new_scope.get_variables():
                    var = new_scope.get_variables()[child.tag]
                    if var.var_type == VarType.INPUT and isinstance(var.value, ComponentValue):
                        continue
                self._execute_node(child, union_scope)

    def _handle_extend(self, extend_name: str, current_scope: Scope, caller_scope: Scope) -> None:
        found = self._find_component(extend_name, current_scope)
        if not found:
            raise Exception(f"Extended component '{extend_name}' not found.")
        base_comp_def, base_decl_scope, base_extend_name, _, _ = found
        if base_comp_def is None:
            raise Exception(f"Cannot extend component '{extend_name}'.")
        union_scope = UnionScope(base_decl_scope, current_scope)
        if base_extend_name:
            self._handle_extend(base_extend_name, union_scope, caller_scope)
        for child in base_comp_def:
            self._execute_node(child, union_scope, caller_scope)
    
    def _add_react_style_quote_logic(self, xml_text: str) -> str:
        """
        Add logic for handling quotes like in React (<Test style={5 + 2} />)

        The regular expression looks for:
        Group 1: Attribute name
        Group 2: Either content in quotes (to skip)
        Group 3: Or content in curly braces (to fix)
        
        Pattern breakdown:
        ([\w:-]+)           - attribute name (including namespace)
        \s*=\s* - equals sign with optional spaces
        (?:                 - start of choice group:
          (["'])(.*?)\2     - option A: quote, text, same quote
          |                 - OR
          ({(?:[^{}]|{[^{}]*})*}) - option B: curly braces (supports one level of nesting for objects {{...}})
        )
        """
        pattern = r'([\w:-]+)\s*=\s*(?:(["\'])(.*?)\2|({(?:[^{}]|{[^{}]*})*}))'

        def replace_match(match: re.Match) -> str:
            attr_name = match.group(1)
            quote_mark = match.group(2)
            quoted_content = match.group(3)
            braced_content = match.group(4)

            if braced_content:
                # If curly braces matched — wrap in quotes
                return f'{attr_name}="{braced_content}"' if '"' not in braced_content else f"{attr_name}='{braced_content}'"
            else:
                # If quotes matched — return as is
                return f'{attr_name}={quote_mark}{quoted_content}{quote_mark}'

        return re.sub(pattern, replace_match, xml_text, flags=re.DOTALL)

    def _replace_special_chars(self, xml_text: str) -> str:
        """
        Replaces special characters with their HTML entities (&amp; &lt; &gt;)
        1. Processing attributes with double quotes: attr="value"
        2. Processing attributes with single quotes: attr='value'
        Find: (name)=(quote)(anything until same quote)(quote)
        """
        pattern = r'([\w\.]+)\s*=\s*(["\'])(.*?)\2'
        def replace_func(m: re.Match) -> str:
            attr_name = m.group(1)
            quote = m.group(2)
            value = m.group(3)
            # Escape special characters inside the value
            safe_value = (value.replace('&', '&amp;')
                            .replace('<', '&lt;')
                            .replace('>', '&gt;'))
            return f'{attr_name}={quote}{safe_value}{quote}'
        return re.sub(pattern, replace_func, xml_text, flags=re.DOTALL)

    def run(self, xml_string: str) -> None:
        if not self.strict_xml:
            xml_string = self._add_react_style_quote_logic(xml_string)
            xml_string = self._replace_special_chars(xml_string)
        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            line, column = e.position
            raise RuntimeError(f"XML Syntax Error at line {line}, col {column}: {e}") from e
        self._execute_node(root, self.global_scope)
