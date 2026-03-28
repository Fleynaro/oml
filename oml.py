import xml.etree.ElementTree as ET
import re

# --- Заглушки системных функций ---
def sys_createPrimitiveBox(**kwargs):
    print(f"[System] createPrimitiveBox called with: {kwargs}")
    return {"type": "Mesh", "name": "Box", "data": kwargs}

def sys_finalizeObject(**kwargs):
    print(f"[System] finalizeObject called with: {kwargs}")
    return {"type": "FinalObject", "data": kwargs}

def sys_path(**kwargs):
    return {"type": "Path", "data": kwargs}

SYSTEM_FUNCTIONS = {
    "createPrimitiveBox": sys_createPrimitiveBox,
    "finalizeObject": sys_finalizeObject,
    "path": sys_path,
}

# --- Управление контекстом (Scope) ---
class Scope:
    """Хранит переменные текущего фрейма и ссылку на родительский scope."""
    def __init__(self, parent=None, name="anonymous"):
        self.parent = parent
        self.name = name
        self.inputs = {}
        self.locals = {}
        self.outputs = {}
        self.calls = [] # context.frame.calls
    
    def get(self, var_name):
        # Порядок разрешения: outputs -> locals -> inputs -> parent
        if var_name in self.outputs: return self.outputs[var_name]
        if var_name in self.locals: return self.locals[var_name]
        if var_name in self.inputs: return self.inputs[var_name]
        if self.parent: return self.parent.get(var_name)
        raise NameError(f"Переменная '{var_name}' не найдена в контексте '{self.name}'")

    def set_local(self, var_name, value):
        self.locals[var_name] = value

    def set_output(self, var_name, value):
        self.outputs[var_name] = value

    def as_dict(self):
        # Для использования внутри eval()
        d = {}
        if self.parent:
            d.update(self.parent.as_dict())
        d.update(self.inputs)
        d.update(self.locals)
        d.update(self.outputs)
        # Добавляем доступ к самому scope как к объекту (для myConsole.borderRadius)
        d[self.name] = self 
        return d

    def __getattr__(self, item):
        # Позволяет обращаться к выходам через точку (myConsole.borderRadius)
        return self.get(item)

# --- Интерпретатор ---
class OMLInterpreter:
    def __init__(self):
        self.registry = {} # Хранилище объявленных компонентов (XML узлы)
        self.global_scope = Scope(name="global")

    def eval_expr(self, expr_str, scope):
        """Вычисляет Python-выражение в текущем контексте."""
        if not isinstance(expr_str, str):
            return expr_str
        try:
            # Ограниченный eval с доступом к переменным scope
            return eval(expr_str, {}, scope.as_dict())
        except Exception as e:
            # Если не получилось как выражение, возвращаем как строку (например, "1 1 1")
            return expr_str

    def eval_fstring(self, text, scope):
        """Интерполирует строки вида 'Sum = {a + b}'."""
        if not text: return ""
        def replace(match):
            expr = match.group(1)
            result = self.eval_expr(expr, scope)
            return str(result)
        return re.sub(r'\{(.*?)\}', replace, text)

    def execute_node(self, node, scope):
        """Рекурсивный обход и выполнение узлов."""
        tag = node.tag

        if tag == "oml" or tag == "Package":
            # Игнорируем мета-теги, просто идем вглубь
            for child in node:
                self.execute_node(child, scope)

        elif tag == "Component":
            # Объявление компонента (сохраняем в реестр, не выполняем)
            comp_name = node.attrib.get("name")
            self.registry[comp_name] = node

        elif tag == "Input":
            name = node.attrib.get("name")
            # Если значение не было передано при вызове (нет в scope.inputs), берем default
            if name not in scope.inputs and "default" in node.attrib:
                val = self.eval_expr(node.attrib["default"], scope)
                scope.inputs[name] = val

        elif tag == "Local":
            name = node.attrib.get("name")
            val = None
            if "set" in node.attrib:
                val = self.eval_expr(node.attrib["set"], scope)
            scope.set_local(name, val)

        elif tag == "Output":
            name = node.attrib.get("name")
            val = None
            if "set" in node.attrib:
                val = self.eval_expr(node.attrib["set"], scope)
            if name:
                scope.set_output(name, val)

        elif tag == "Call":
            # Вызов системной функции Python
            func_name = node.attrib.get("name")
            params_str = node.attrib.get("params", "{}")
            ret_var = node.attrib.get("return")

            # Парсим псевдо-синтаксис словаря (упрощенно для прототипа)
            # В реальности тут нужен более умный парсер { size, borderRadius }
            params_dict = self.eval_expr(params_str.replace("{", "{'").replace(":", "':").replace(", ", ", '"), scope) if "{" in params_str else {}
            if not isinstance(params_dict, dict): params_dict = {}

            if func_name in SYSTEM_FUNCTIONS:
                result = SYSTEM_FUNCTIONS[func_name](**params_dict)
                scope.calls.append(result)
                if ret_var:
                    scope.set_local(ret_var, result) # Сохраняем результат в локальную переменную (например, e)
            else:
                print(f"[Error] System function '{func_name}' not found.")

        elif tag == "DebugPrint":
            text = node.attrib.get("text", "")
            print(f"[Debug] {self.eval_fstring(text, scope)}")

        else:
            # Если тег не встроенный, значит это вызов пользовательского компонента
            self.call_component(tag, node, scope)

    def call_component(self, comp_name, call_node, parent_scope):
        if comp_name not in self.registry:
            # Для прототипа: если компонента нет, игнорируем (или можно кидать ошибку)
            return

        comp_def = self.registry[comp_name]
        
        # 1. Создаем новый фрейм (Scope)
        instance_name = call_node.attrib.get("name", f"anon_{comp_name}")
        new_scope = Scope(parent=parent_scope, name=instance_name)

        # 2. Передаем атрибуты вызова как Input
        for attr_name, attr_val in call_node.attrib.items():
            if attr_name not in ["name"]: # Пропускаем служебные
                new_scope.inputs[attr_name] = self.eval_expr(attr_val, parent_scope)

        # 3. Обрабатываем наследование (extend)
        extend_name = comp_def.attrib.get("extend")
        if extend_name and extend_name in self.registry:
            # Выполняем тело родителя в текущем контексте
            for child in self.registry[extend_name]:
                self.execute_node(child, new_scope)

        # 4. Выполняем тело самого компонента
        for child in comp_def:
            self.execute_node(child, new_scope)

        # 5. Выполняем дочерние теги ВЫЗОВА (создавая тот самый контекст вызова)
        # Они выполняются в рамках new_scope, поэтому видят outputs этого компонента!
        for child in call_node:
            self.execute_node(child, new_scope)

        # 6. Сохраняем результаты
        parent_scope.calls.append(new_scope.outputs)
        
        # Если при вызове было указано имя (напр. <ConsoleComp name="myConsole">), 
        # сохраняем весь scope как локальную переменную родителя
        if "name" in call_node.attrib:
            parent_scope.set_local(instance_name, new_scope)

    def run(self, xml_string):
        root = ET.fromstring(xml_string)
        self.execute_node(root, self.global_scope)

# --- Тестовый запуск ---
if __name__ == "__main__":
    test_xml = """
    <oml version="1.0">
        <Component name="SumTwoNumbers">
            <Input name="a" type="int" />
            <Input name="b" type="int" />
            <Local name="c" type="int" set="a + b" />
            <Output name="result" set="c" />
        </Component>

        <Component name="MathModule">
            <SumTwoNumbers name="sumRes" a="10" b="15">
                <DebugPrint text="Внутри вызова: result = {result}"/>
            </SumTwoNumbers>
            
            <DebugPrint text="В родителе: sumRes.result = {sumRes.result}"/>
        </Component>

        <MathModule />
    </oml>
    """
    
    interpreter = OMLInterpreter()
    interpreter.run(test_xml)