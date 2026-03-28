from typing import Any, Callable, Dict
import unittest
import textwrap

from interpreter import OMLInterpreter

# Assuming OMLInterpreter is imported from your main module
# from your_module import OMLInterpreter

class BaseOMLTestCase(unittest.TestCase):
    """
    Base test case providing a helper method to execute OML code
    and retrieve the debug text for assertions.
    """
    def run_oml(self, xml_content, custom_data_types: Dict[str, Any] = {}, system_functions: Dict[str, Callable] = None):
        # Wrap the specific component/test code in the root <oml> tag
        full_xml = f'<oml version="1.0">\n{xml_content}\n</oml>'
        interpreter = OMLInterpreter(custom_data_types=custom_data_types, system_functions=system_functions)
        interpreter.run(full_xml)
        
        # Strip trailing newlines to make assertions cleaner
        return interpreter.testPrint.strip()

# ==========================================
# CATEGORY: Basic I/O and Variables
# ==========================================
class TestBasicMechanics(BaseOMLTestCase):
    
    def test_basic_input_output_evaluation(self):
        """
        Tests basic evaluation of mathematical expressions, 
        passing inputs to components, and retrieving outputs.
        """
        xml = """
        <Component name={'SumTwo' + 'Numbers'}>
            <Input name="a" type="int" />
            <Input name="b" type="int" />
            <Input name="mul" type="bool" default="false" />
            <Local name="c" type="int" />
            <Set name="c" type="int" set={a + b * (10 if mul else 1)} />
            <Output name="result" set={c} />
        </Component>
        <Component name="App">
            <Local name="someVar" set="hello" />
            <SumTwoNumbers name="r" a="10" b={15}>
                <TestPrint text="[Inside 1] result = {result} {someVar}"/>
                <TestPrint text="[Inside 2] result = {r.result} {someVar}"/>
            </SumTwoNumbers>
            <TestPrint text="[Outside] result = {r.result} {someVar}"/>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        [Inside 1] result = 25 hello
        [Inside 2] result = 25 hello
        [Outside] result = 25 hello
        """).strip()
        
        output = self.run_oml(xml)
        self.assertMultiLineEqual(output, expected)


# ==========================================
# CATEGORY: Custom Data Types and Conversions
# ==========================================
class TestCustomDataTypes(BaseOMLTestCase):

    class Vector4:
        def __init__(self, *args):
            if len(args) == 1 and isinstance(args[0], str):
                vals = list(map(float, args[0].split()))
            elif len(args) > 1:
                vals = list(map(float, args))
            elif len(args) == 1:
                vals = [float(args[0])] * 4
            else:
                vals = [0.0] * 4
            self.x, self.y, self.z, self.w = vals[:4]
        
        def __str__(self):
            return f"Vector4({self.x}, {self.y}, {self.z}, {self.w})"

    def test_vector_initialization_from_string_and_number(self):
        """
        Tests that custom types (Vector4) can be initialized via 
        different input formats (string vs single number) and 
        correctly accessed in expressions.
        """
        xml = """
        <Component name="App">
            <Input name="v1" type="Vector4" default="1 2 3 4" />
            <Input name="v2" type="Vector4" default={5.0} />
            
            <TestPrint text="v1: {v1}" />
            <TestPrint text="v2: {v2}" />
            <TestPrint text="sum_x: {v1.x + v2.x}" />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        v1: Vector4(1.0, 2.0, 3.0, 4.0)
        v2: Vector4(5.0, 5.0, 5.0, 5.0)
        sum_x: 6.0
        """).strip()
        
        custom_types = {"Vector4": self.Vector4}
        output = self.run_oml(xml, custom_data_types=custom_types)
        
        self.assertMultiLineEqual(output, expected)

    def test_vector_assignment_in_local_scope(self):
        """
        Verifies that custom types can be instantiated and 
        re-assigned within Local variables.
        """
        xml = """
        <Component name="App">
            <Local name="pos" type="Vector4" set={Vector4(10, 20, 30, 40)} />
            <TestPrint text="Initial: {pos.y}" />
            
            <Local name="pos" set={Vector4(0)} />
            <TestPrint text="Reset: {pos.y}" />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Initial: 20.0
        Reset: 0.0
        """).strip()
        
        custom_types = {"Vector4": self.Vector4}
        output = self.run_oml(xml, custom_data_types=custom_types)
        
        self.assertMultiLineEqual(output, expected)


# ==========================================
# CATEGORY: Control Flow
# ==========================================
class TestControlFlow(BaseOMLTestCase):

    def test_if_else_branch_true(self):
        """Tests the If node when the condition evaluates to True."""
        xml = """
        <Component name="App">
            <Local name="flag" set={True} />
            <If condition={flag}>
                <TestPrint text="True branch executed" />
                <Else>
                    <TestPrint text="False branch executed" />
                </Else>
            </If>
        </Component>
        <App />
        """
        expected = "True branch executed"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_if_else_branch_false(self):
        """Tests the If/Else node when the condition evaluates to False."""
        xml = """
        <Component name="App">
            <Local name="flag" set={False} />
            <If condition={flag}>
                <TestPrint text="True branch executed" />
                <Else>
                    <TestPrint text="False branch executed" />
                </Else>
            </If>
        </Component>
        <App />
        """
        expected = "False branch executed"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_repeat_for_loop(self):
        """Tests the Repeat node iterating over a range of numbers."""
        xml = """
        <Component name="App">
            <Repeat name="i" from={1} to={3} step={1}>
                <Local name="sq" set={i * i} />
                <TestPrint text="Step {i}: Square is {sq}" />
            </Repeat>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Step 1: Square is 1
        Step 2: Square is 4
        Step 3: Square is 9
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_repeat_while_loop(self):
        """Tests the Repeat node using a while-condition."""
        xml = """
        <Component name="App">
            <Local name="counter" set={0} />
            <Repeat while={counter != 3}>
                <TestPrint text="Iteration {counter}" />
                <Local name="counter" set={counter + 1} />
            </Repeat>
            <TestPrint text={f"Finished at {counter}"} />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Iteration 0
        Iteration 1
        Iteration 2
        Finished at 3
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)


# ==========================================
# CATEGORY: Inheritance and Lifecycle
# ==========================================
class TestInheritanceAndLifecycle(BaseOMLTestCase):

    def test_component_inheritance_chain(self):
        """
        Tests that components can extend other components, 
        inheriting and executing parent nodes sequentially.
        """
        xml = """
        <Component name="SuperBase">
            <Input name="a" type="int" />
            <TestPrint text="--- SuperBase {a} ---" />
        </Component>
        <Component name="Base" extend="SuperBase">
            <Input name="b" type="int" />
            <TestPrint text="--- Base {a} {b} ---" />
        </Component>
        <Component name="Derived" extend="Base">
            <Input name="c" type="int" />
            <TestPrint text="--- Derived {a} {b} {c} ---" />
        </Component>
        <Component name="App">
            <Derived a={1} b={2} c={3} />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        --- SuperBase 1 ---
        --- Base 1 2 ---
        --- Derived 1 2 3 ---
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_post_execute_lifecycle(self):
        """
        Tests that PostExecute blocks run *after* the main body,
        and variables are correctly modified and retained between lifecycle stages.
        """
        xml = """
        <Component name="Base">
            <Local name="var" type="int" set={1} />
            <PostExecute>
                <TestPrint text="Base PostExecute: {var}" />
            </PostExecute>
        </Component>
        <Component name="Derived" extend="Base">
            <TestPrint text="Derived Init: {var}" />
            <Local name="var" set={2} />
            <PostExecute>
                <TestPrint text="Derived PostExecute: {var}" />
            </PostExecute>
        </Component>
        <Component name="App">
            <Derived />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Derived Init: 1
        Base PostExecute: 2
        Derived PostExecute: 2
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_triple_inheritance_post_execute(self):
        """
        Tests a 3-level inheritance chain: GrandParent -> Parent -> Child.
        All PostExecute blocks must fire in order.
        """
        xml = """
        <Component name="A">
            <PostExecute><TestPrint text="Post A" /></PostExecute>
        </Component>
        <Component name="B" extend="A">
            <PostExecute><TestPrint text="Post B" /></PostExecute>
        </Component>
        <Component name="C" extend="B">
            <PostExecute><TestPrint text="Post C" /></PostExecute>
        </Component>
        <Component name="App">
            <C />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Post A
        Post B
        Post C
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_inheritance_with_base_variable_closure(self):
        """
        This test verifies component inheritance where the child component extends
        a base defined by a variable closure. It ensures that the 'base' variable is
        captured as a read-only (!) closure, meaning it can be resolved to identify
        the parent component but CANNOT be modified or re-assigned from within
        the extending component.
        """
        xml = """
        <Component name="A">
            <Output name="base" set="B" />
            <Component name={base} output={True}>
                <!-- NOTE: You can't change 'base' here -->
                <PostExecute>
                    <TestPrint text="Post {base}" />
                </PostExecute>
            </Component>
        </Component>
        <A name="A" />
        <Component name="C" extend="A.{A.base}">
            <PostExecute>
                <TestPrint text="Post C" />
            </PostExecute>
        </Component>
        <Component name="App">
            <C />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Post B
        Post C
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)


# ==========================================
# CATEGORY: Scoping and Visibility
# ==========================================
class TestScopingAndVisibility(BaseOMLTestCase):

    def test_lexical_scoping_from_parent(self):
        """
        Tests that a nested component can read variables declared in 
        the component where it is instantiated (closure behavior).
        """
        xml = """
        <Component name="ParentScopeTest">
            <Local name="sharedType" set="Spline" />
            <Component name="Point">
                <TestPrint text="Point sees sharedType: {sharedType}" /> 
                <TestPrint text="Point sees appVar: {appVar}" /> 
            </Component>
            <Component name="Box">
                <Local name="appVar" set="hello" />
                <Point />
            </Component>
            <Box />
        </Component>
        <Component name="App">
            <ParentScopeTest />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Point sees sharedType: Spline
        Point sees appVar: None
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_library_redefinition_by_instance(self):
        """
        Tests that a library can be redefined by an instance.
        """
        xml = """
        <Component name="Library">
            <Input name="config" type="str" />
            <Component name="LibComp" output="true">
                <TestPrint text="LibComp uses config: {config}" /> 
            </Component>
        </Component>
        <Library name="Library" config="conf" />
        <Component name="App">
            <Library.LibComp />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        LibComp uses config: conf
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_instance_name_resolution_and_child_access(self):
        """
        Tests accessing a sub-component through an instance name.
        Scenario: 'Path' defines 'Point'. We create an instance 'mypath'.
        We then call 'mypath.Point', which should inherit the context of 'mypath'.
        """
        xml = """
        <Component name="Path">
            <Input name="pathType" default="Linear" />
            <Component name="Point" output="true">
                <Input name="id" />
                <TestPrint text="Point {id} in {pathType} path" />
            </Component>
        </Component>
        <Component name="App">
            <Path name="myPath" pathType="Bezier" />
            <myPath.Point id="A" />
        </Component>
        <App />
        """
        expected = "Point A in Bezier path"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_output_visibility_instance_access_success(self):
        """
        Tests that 'output=true' allows access ONLY through an instance.
        """
        xml = """
        <Component name="Path">
            <Component name="Point" output="true">
                <TestPrint text="Point Created" />
            </Component>
        </Component>
        <Component name="App">
            <Path name="p">
                <Point />
            </Path>
            <p.Point />
        </Component>
        <App />
        """
        expected = "Point Created\nPoint Created"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_output_visibility_global_access_fails(self):
        """
        Tests that 'output=true' components CANNOT be accessed via 
        the Global Class Path. It must raise an exception.
        """
        xml = """
        <Component name="Path">
            <Component name="Point" output="true">
                <TestPrint text="Should not see this" />
            </Component>
        </Component>
        <Component name="App">
            <Path.Point />
        </Component>
        <App />
        """
        # We expect an Exception here because Point is 'output' only, 
        # but called via Global Path 'Path.Point'
        with self.assertRaisesRegex(Exception, "Component 'Path.Point' not found. Try to check accessibility."):
            self.run_oml(xml)

    def test_private_visibility_access_fails(self):
        """
        Tests that 'private' components are invisible to everyone outside 
        the parent component.
        """
        xml = """
        <Component name="SecretBox">
            <Component name="HiddenInternal" output="false">
                <TestPrint text="Hidden" />
            </Component>
            <HiddenInternal />
        </Component>
        <Component name="App">
            <SecretBox name="box" />
            <box.HiddenInternal />
        </Component>
        <App />
        """
        # Internal print will happen, but the external call 'box.HiddenInternal' fails.
        with self.assertRaisesRegex(Exception, "Component 'box.HiddenInternal' not found. Try to check accessibility."):
            self.run_oml(xml)

    def test_nested_component_dot_notation(self):
        """
        Tests accessing a component inside another component 
        using dot notation: Outer.Inner
        This logic is similar to the 'namespace' concept.
        """
        xml = """
        <Component name="Universe">
            <Local name="sign" set="!" />

            <!-- Definition way 1 -->
            <Output name="Galaxy" type="struct">
                <Output name="System" type="struct">
                    <Component name="Star">
                        <TestPrint text="Star{sign}" />
                    </Component>
                </Output>
                <Component name="Planet">
                    <TestPrint text="Planet{sign}" />
                </Component>
            </Output>

            <!-- Definition way 2 -->
            <Component name="Galaxy.System.Satellite" output="true">
                <TestPrint text="Satellite{sign}" />
            </Component>

            <!-- Definition way 3 -->
            <Output name="Galaxy.System.Earth" type="component">
                <TestPrint text="Earth{sign}" />
            </Output>
        </Component>
        <Universe name="Universe" />
        <Component name="App">
            <Universe.Galaxy.System.Star />
            <Universe.Galaxy.Planet />
            <Universe.Galaxy.System.Satellite />
            <Universe.Galaxy.System.Earth />
        </Component>
        <App />
        """
        expected = "Star!\nPlanet!\nSatellite!\nEarth!"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_local_shadowing_input(self):
        """
        Verifies that a Local variable takes precedence over an Input 
        with the same name inside the component scope.
        """
        xml = """
        <Component name="ShadowComp">
            <Input name="x" type="int" />
            <Output name="x" set={x * 10} />
            <TestPrint text="Value of x: {x}" />
        </Component>
        <Component name="App">
            <ShadowComp x={5} />
        </Component>
        <App />
        """
        # Input is 5, but Local redefines it as 5 * 10
        expected = "Value of x: 50"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

# ==========================================
# CATEGORY: System Calls
# ==========================================
class TestSystemCalls(BaseOMLTestCase):

    def test_call_simple_no_params(self):
        """
        Tests a basic call to a system function without any parameters.
        Verifies that the function is actually executed.
        """
        log = []
        def sys_ping():
            log.append("pong")
            return "ok"

        xml = """
        <Component name="App">
            <Call name="ping" />
        </Component>
        <App />
        """
        
        self.run_oml(xml, system_functions={"ping": sys_ping})
        self.assertEqual(log, ["pong"])

    def test_call_with_static_parameters(self):
        """
        Tests passing multiple static key-value parameters to a system function.
        """
        log = []
        def sys_create_box(width=0, height=0):
            log.append(f"Box {width}x{height}")

        xml = """
        <Component name="App">
            <Call name="createBox" params={width=10, height=20} />
        </Component>
        <App />
        """
        
        self.run_oml(xml, system_functions={"createBox": sys_create_box})
        self.assertEqual(log, ["Box 10x20"])

    def test_call_with_dynamic_expressions(self):
        """
        Verifies that expressions inside 'params' are evaluated 
        using the current OML scope before being passed to Python.
        """
        log = []
        def sys_move(distance=0):
            log.append(f"Moved {distance}")

        xml = """
        <Component name="App">
            <Local name="offset" set={5} />
            <Local name="multiplier" set={3} />
            <Call name="move" params={distance=offset * multiplier} />
        </Component>
        <App />
        """
        
        # distance should be 5 * 3 = 15
        self.run_oml(xml, system_functions={"move": sys_move})
        self.assertEqual(log, ["Moved 15"])

    def test_call_return_to_local_variable(self):
        """
        Tests that the 'return' attribute correctly stores the Python 
        function result into a specified OML local variable.
        """
        def sys_get_version():
            return "1.2.3"

        xml = """
        <Component name="App">
            <Call name="getVersion" return="ver" />
            <TestPrint text="System Version: {ver}" />
        </Component>
        <App />
        """
        
        output = self.run_oml(xml, system_functions={"getVersion": sys_get_version})
        self.assertMultiLineEqual(output, "System Version: 1.2.3")

    def test_call_return_complex_object(self):
        """
        Tests returning a dictionary from Python and accessing 
        its fields in OML via dot notation.
        """
        def sys_get_user():
            return {"id": 42, "name": "Admin"}

        xml = """
        <Component name="App">
            <Call name="getUser" return="user" />
            <TestPrint text="ID: {user.id}, Name: {user.name}" />
        </Component>
        <App />
        """
        
        output = self.run_oml(xml, system_functions={"getUser": sys_get_user})
        self.assertMultiLineEqual(output, "ID: 42, Name: Admin")

    def test_call_scoping_isolation(self):
        """
        Ensures that if a system function is called inside a nested component,
        it still has access to that component's inputs and locals via params.
        """
        log = []
        def sys_notify(msg=""):
            log.append(msg)

        xml = """
        <Component name="Worker">
            <Input name="id" />
            <Local name="status" set="active" />
            <Call name="notify" params={msg='Worker ' + str(id) + ' is ' + status} />
        </Component>
        <Component name="App">
            <Worker id="101" />
        </Component>
        <App />
        """
        
        self.run_oml(xml, system_functions={"notify": sys_notify})
        self.assertEqual(log, ["Worker 101 is active"])

    def test_call_error_missing_function(self):
        """
        Checks how the interpreter handles calls to unregistered functions.
        (Assuming the interpreter prints an error to debugText or console).
        """
        xml = """
        <Component name="App">
            <Call name="nonExistentFunc" />
        </Component>
        <App />
        """
        with self.assertRaisesRegex(ValueError, "System function 'nonExistentFunc' not found."):
            self.run_oml(xml, system_functions={})

# ==========================================
# CATEGORY: Advanced Features
# ==========================================
class TestAdvancedFeatures(BaseOMLTestCase):

    def test_lambda_component_inputs(self):
        """
        Tests dependency injection (passing a Component as an Input),
        verifying it acts like a lambda/callback with its own scope.
        """
        xml = """
        <Component name="Test">
            <Input name="SumInput" type="component" />
            <Output name="varTwo" set="world" />
            <SumInput a={1} b={2}>
                <TestPrint text="Lambda result: {result}" />
            </SumInput>
        </Component>
        <Component name="App">
            <Local name="varOne" set="hello" />

            <!-- Way 1 -->
            <Test>
                <SumInput>
                    <Input name="a" type="int" />
                    <Input name="b" type="int" />
                    <Output name="result" set={a + b} />
                    <TestPrint text="Lambda closure: {varOne} {varTwo}" />
                </SumInput>
                <TestPrint text="Output scope: {varOne} {varTwo}" />
            </Test>

            <!-- Way 2 -->
            <Local name="SumInput" type="component">
                <Input name="a" type="int" />
                <Input name="b" type="int" />
                <Output name="result" set={a + b} />
                <TestPrint text="Lambda closure 2: {varOne}" />
            </Local>
            <Test SumInput={SumInput} />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Lambda closure: hello None
        Lambda result: 3
        Output scope: hello world
        Lambda closure 2: hello
        Lambda result: 3
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_struct_inputs_and_outputs(self):
        """
        Tests complex data types (structs), allowing dot notation 
        for nested variables.
        """
        xml = """
        <Component name="Multiplier">
            <Input name="posInput" type="struct">
                <Input name="x" type="int" default={0} />
                <Input name="y" type="int" default={2} />
            </Input>
            <Input name="k" type="int" />
            <Output name="pos" type="struct">
                <Output name="x" set={posInput.x * k} />
                <Output name="y" set={posInput.y * k} />
            </Output>
        </Component>
        <Component name="App">
            <Multiplier name="result" posInput.x={5} k={3} />
            <TestPrint text="Result X: {result.pos.x}, Y: {result.pos.y}" />
        </Component>
        <App />
        """
        expected = "Result X: 15, Y: 6"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_context_variables_propagation(self):
        """
        Tests context="true" variables, ensuring they propagate deeply 
        down the component tree automatically.
        """
        xml = """
        <Component name="MyContextDef">
            <Output name="Ctx" type="struct" context="true">
                <Output name="val" set="secret_code" />
            </Output>
        </Component>
        <Component name="DeepReader">
            <TestPrint text="Deep Reader sees: {Ctx.val}" />
        </Component>
        <Component name="Reader">
            <TestPrint text="Reader sees: {Ctx.val}" />
            <DeepReader />
        </Component>
        <Component name="App">
            <MyContextDef>
                <TestPrint text="Root sees: {Ctx.val}" />
                <Reader />
            </MyContextDef>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Root sees: secret_code
        Reader sees: secret_code
        Deep Reader sees: secret_code
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_context_variable_masking(self):
        """
        Tests that a nested Context with the same name masks the outer one 
        for its children, but doesn't destroy the outer one for siblings.
        """
        xml = """
        <Component name="Provider">
            <Input name="val" />
            <Output name="Store" type="struct" context="true">
                <Output name="data" set={val} />
            </Output>
        </Component>
        <Component name="Consumer">
            <TestPrint text="Consumer sees: {Store.data}" />
        </Component>
        <Component name="App">
            <Provider val="OUTER">
                <Consumer />
                <Provider val="INNER">
                    <Consumer />
                </Provider>
                <Consumer />
            </Provider>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Consumer sees: OUTER
        Consumer sees: INNER
        Consumer sees: OUTER
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_callback_wrapped_in_provider_context_availability(self):
        """
        Verifies that a component passed as a callback (child) can correctly access
        the context provided by a wrapper inside the receiver's definition. The test
        ensures that the Provider correctly scopes the Store data only to the components
        executed within its body, specifically when those components are injected via a callback.
        """
        xml = """
        <Component name="Provider">
            <Output name="Store" type="struct" context="true">
                <Output name="data" set="Context" />
            </Output>
        </Component>
        <Component name="Consumer">
            <TestPrint text="Consumer sees: {Store.data}" />
        </Component>
        <Component name="Test">
            <Input name="callback" type="component" children="true" />
            <Provider>
                <callback />
            </Provider>
        </Component>
        <Component name="App">
            <Consumer />
            <Test>
                <Consumer />
            </Test>
            <Consumer />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Consumer sees: None
        Consumer sees: Context
        Consumer sees: None
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_children_as_inputs(self):
        """
        Tests capturing inner XML children via children="true" and evaluating them.
        """
        xml = """
        <Component name="PrimitiveBox">
            <Output name="e" set="name" />
            <TestPrint text="Created Box: {name}" />
        </Component>
        <Component name="Group">
            <TestPrint text="Group executing children..." />
            <Input name="elements" type="component" children="true" />
            <elements PrimitiveBox={PrimitiveBox} />
        </Component>
        <Component name="App">
            <Group>
                <Repeat from={1} to={2}>
                    <PrimitiveBox name="box{i}" />
                </Repeat>
            </Group>
        </Component>
        <App />
        """
        # Exact expected output depends on how your `type="children"` implementation handles execution.
        # This mirrors the logic where children are executed when the parent is evaluated.
        expected = textwrap.dedent("""
        Group executing children...
        Created Box: box1
        Created Box: box2
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_component_injection_and_state_accumulation(self):
        """
        Verifies that a component (Point) can be passed as a prop and 
        accumulate data into a parent-level array (posArray) during 
        the instantiation of children.
        """
        xml = """
        <Component name="Path">
            <Input name="PointsInput" type="component" children="true" />
            <Local name="posArray" set={[]} />  
            <Component name="Point" output="true">
                <Input name="pos" type="float" default={0} />
                <Local name="posArray" set={posArray + [pos]} />
            </Component>
            <PointsInput Point={Point}>
                <TestPrint text="Point calls count: {len(calls())}"/>
            </PointsInput>
            <TestPrint text="Path: {posArray}"/>
        </Component>
        <Component name="App">
            <Local name="posArray" set={[1, 2]} />
            <Path>
                <Repeat from={0} to={len(posArray) - 1}>
                    <Point pos={posArray[i]} />
                </Repeat>
            </Path>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Point calls count: 2
        Path: [1.0, 2.0]
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_assert_trigger_exception(self):
        """
        Verifies that Assert raises an error when the condition fails.
        """
        xml = """
        <Component name="App">
            <Local name="value" set={10} />
            <Assert condition={value == 20} text="Value must be 20!" />
            <TestPrint text="This should not be printed" />
        </Component>
        <App />
        """
        with self.assertRaisesRegex(Exception, "Value must be 20!"):
            self.run_oml(xml)

class TestHigherOrderMechanics(BaseOMLTestCase):

    def test_component_passing_chain(self):
        """
        Passes a component 'A' into component 'B', which then passes 'A' into 'C'.
        Tests the stability of ComponentInput objects during re-passing.
        """
        xml = """
        <Component name="Leaf">
            <Input name="callback" type="component" />
            <TestPrint text="Leaf: calling callback..." />
            <callback />
        </Component>
        <Component name="Proxy">
            <Input name="passedComp" type="component" />
            <TestPrint text="Proxy: forwarding..." />
            <Leaf callback={passedComp} />
        </Component>
        <Component name="App">
            <Proxy>
                <passedComp>
                    <TestPrint text="Success: Final Callback executed!" />
                </passedComp>
            </Proxy>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Proxy: forwarding...
        Leaf: calling callback...
        Success: Final Callback executed!
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

class TestRecursion(BaseOMLTestCase):

    def test_factorial_recursion(self):
        """
        Classic recursion test. Calculates 5! (120) by recursive calls.
        Tests if each recursive step maintains its own 'n' and 'sub.val'.
        """
        xml = """
        <Component name="Factorial">
            <Input name="n" type="int" />
            <If condition={n <= 1}>
                <Output name="res" set={1} />
                <Else>
                    <Factorial n={n - 1} name="sub" />
                    <Output name="res" set={n * sub.res} />
                </Else>
            </If>
        </Component>
        <Component name="App">
            <Factorial n={5} name="f" />
            <TestPrint text="5! is {f.res}" />
        </Component>
        <App />
        """
        expected = "5! is 120"
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_recursive_tree_generation(self):
        """
        Simulates a tree structure generation. 
        Each branch calls itself twice with reduced depth.
        """
        xml = """
        <Component name="Branch">
            <Input name="depth" type="int" />
            <If condition={depth > 0}>
                <TestPrint text="Branch at depth {depth}" />
                <Branch depth={depth - 1} />
                <Branch depth={depth - 1} />
            </If>
        </Component>
        <Component name="App">
            <Branch depth={2} />
        </Component>
        <App />
        """
        # Depth 2 calls two Depth 1. Each Depth 1 calls two Depth 0 (which do nothing).
        expected = textwrap.dedent("""
        Branch at depth 2
        Branch at depth 1
        Branch at depth 1
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

class TestIntegrationStress(BaseOMLTestCase):
    def test_recursive_lambda_with_context_accumulation(self):
        """
        SCENARIO: THE RECURSIVE REDUCER
        We pass a 'logic' lambda into a 'RecursiveAccumulator'. 
        The lambda uses a Context variable to sum up values.
        
        GOAL: Break the scope. Ensure the lambda (defined in App) 
        correctly updates the Context while being called from different 
        levels of recursion inside the component.
        """
        xml = """
        <Component name="ContextStore">
            <Output name="Storage" type="struct" context="true">
                <Output name="total" set={0} />
            </Output>
        </Component>

        <Component name="RecursiveAccumulator">
            <Input name="n" type="int" />
            <Input name="logic" type="component" />
            
            <If condition={n > 0}>
                <logic val={n} />
                <RecursiveAccumulator n={n - 1} logic={logic} />
            </If>
        </Component>

        <Component name="App">
            <ContextStore>
                <RecursiveAccumulator n={4}>
                    <logic>
                        <Input name="val" type="int" />
                        <!-- We can define the context as input for better clarity -->
                        <Input name="Storage" />
                        <!-- We can change the Storage fields by reference -->
                        <Local name="Storage.total" set={Storage.total + val}/>
                        <TestPrint text="Added {val}, Current Total: {Storage.total}" />
                    </logic>
                </RecursiveAccumulator>
                <TestPrint text="Final Result: {Storage.total}" />
            </ContextStore>
        </Component>
        <App />
        """
        # Sum of 4+3+2+1 = 10
        expected = textwrap.dedent("""
        Added 4, Current Total: 4
        Added 3, Current Total: 7
        Added 2, Current Total: 9
        Added 1, Current Total: 10
        Final Result: 10
        """).strip()
        
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_diamond_inheritance_with_post_execute_and_system_calls(self):
        """
        SCENARIO: THE LIFECYCLE LABYRINTH
        A complex inheritance chain where Base, Mid, and Derived all have 
        PostExecute blocks and System Calls. 
        
        GOAL: Break the execution order. Verify that PostExecute from 
        Base runs BEFORE PostExecute of Derived, and that shadowed 
        variables ('mode') are correctly resolved during the System Call.
        """
        log = []
        def sys_audit(label, val):
            log.append(f"[{label}] {val}")

        xml = """
        <Component name="Base">
            <Input name="mode" default="SILENT" />
            <PostExecute>
                <Call name="audit" params={label="BASE_POST", val=mode} />
            </PostExecute>
        </Component>

        <Component name="Mid" extend="Base">
            <Local name="mode" set="VERBOSE" />
            <TestPrint text="Mid init mode: {mode}" />
        </Component>

        <Component name="Derived" extend="Mid">
            <PostExecute>
                <TestPrint text="Derived post-exec start" />
                <Call name="audit" params={label='DERIVED_POST', val=mode} />
            </PostExecute>
        </Component>

        <Component name="App">
            <Derived mode="EXTERN" />
        </Component>
        <App />
        """
        # Note: Mid shadows 'mode' with 'VERBOSE'. 
        # Base.PostExecute should see 'VERBOSE' because it works on the final scope.
        self.run_oml(xml, system_functions={"audit": sys_audit})
        
        expected_log = [
            "[BASE_POST] VERBOSE",
            "[DERIVED_POST] VERBOSE"
        ]
        self.assertEqual(log, expected_log)

    def test_component_extension_and_nested_injection(self):
        """
        Verifies complex component hierarchy: inheritance (extend), 
        dynamic component injection into children-handling inputs, 
        and the execution order of lifecycle hooks across nested scopes.
        """
        xml = """
        <Component name="HouseBuilder">
            <Input name="ObjectsInput" type="component" children="true" />

            <Component name="HousePart">
                <Local name="part_name" set="unknown" />
                <Component name="Init">
                    <Local name="part_name" set={part_name} />
                </Component>
                <PostExecute>
                    <TestPrint text="{part_name} built" />
                </PostExecute>
            </Component>

            <Component name="Object">
                <Input name="pos" type="float" default={0} />
            </Component>

            <Component name="Floor" extend="HousePart" output="true">
                <Init part_name="Floor" />
                <Component name="Chair" extend="Object" output="true">
                    <TestPrint text="Chair: {pos}" />
                </Component>
                <Component name="Table" extend="Object" output="true">
                    <TestPrint text="Table: {pos}" />
                </Component>
            </Component>

            <Component name="Wall" extend="HousePart" output="true">
                <Init part_name="Wall" />
                <Component name="Window" extend="Object" output="true">
                    <TestPrint text="Window: {pos}" />
                </Component>
            </Component>

            <TestPrint text="Start building" />
            <ObjectsInput Floor={Floor} Wall={Wall} />
            <TestPrint text="House built" />
        </Component>
        <Component name="App">
            <HouseBuilder>
                <Floor>
                    <Chair />
                    <Table pos={2} />
                </Floor>
                <Wall>
                    <Window pos={10} />
                    <Window pos={11} />
                </Wall>
            </HouseBuilder>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Start building
        Floor built
        Chair: 0.0
        Table: 2.0
        Wall built
        Window: 10.0
        Window: 11.0
        House built
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_inheritance_method_overriding(self):
        """
        SCENARIO: Polymorphism.
        'Animal' has a method 'Speak'. 'Dog' extends 'Animal' and overrides 'Speak'.
        """
        xml = """
        <Component name="Animal">
            <Input name="name_attr" />
            <Component name="speak" output="true">
                <TestPrint text="{name_attr} makes a sound" />
            </Component>
        </Component>

        <Component name="Dog" extend="Animal">
            <Component name="speak" output="true">
                <TestPrint text="{name_attr} barks: Woof!" />
            </Component>
        </Component>

        <Component name="App">
            <Animal name="generic" name_attr="Thing" /> 
            <Dog name="myDog" name_attr="Rex" />
            
            <generic.speak />
            <myDog>
                <speak />
                <generic>
                    <speak />
                </generic>
                <speak />
            </myDog>
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Thing makes a sound
        Rex barks: Woof!
        Thing makes a sound
        Rex barks: Woof!
        """).strip()
        self.assertMultiLineEqual(self.run_oml(xml), expected)
    
    def test_dependency_injection_method_call(self):
        """
        SCENARIO: Object passing.
        A component instance is passed to another component as an input, 
        and the receiver calls a method on that passed object.
        """
        xml = """
        <Component name="Service">
            <Input name="prefix" />
            <Component name="execute" output="true">
                <TestPrint text="{prefix}: Action performed" />
            </Component>
        </Component>

        <Component name="Consumer">
            <Input name="provider" type="component" />
            <Component name="run" output="true">
                <provider.execute />
            </Component>
        </Component>

        <Component name="App">
            <Service name="myService" prefix="LOG" />
            <Consumer name="client" provider={myService} />
            <client.run />
        </Component>
        <App />
        """
        expected = "LOG: Action performed"
        self.assertEqual(self.run_oml(xml).strip(), expected)

    def test_nested_object_factory_chain(self):
        """
        SCENARIO: Method Chaining / Factory Pattern.
        A method returns a component instance, which in turn has a method 
        returning another instance.
        """
        xml = """
        <Component name="Task">
            <Input name="id" />
            <Component name="complete" output="true">
                <TestPrint text="Task {id} is done" />
            </Component>
        </Component>

        <Component name="Service">
            <Component name="create_task" output="true">
                <Task name="task" id="42" />
                <Output set={task} />
            </Component>
        </Component>

        <Component name="Factory">
            <Component name="get_service" output="true">
                <Service name="service" />
                <Output set={service} />
            </Component>
        </Component>

        <Component name="App">
            <Factory>
                <get_service>
                    <create_task>
                        <complete />
                    </create_task>
                </get_service>
            </Factory>
        </Component>
        <App />
        """
        expected = "Task 42 is done"
        self.assertEqual(self.run_oml(xml).strip(), expected)

    def test_callback_mechanism(self):
        """
        SCENARIO: Callbacks.
        Component A passes its own method to Component B. 
        Component B executes the passed method (callback) when a task is finished.
        """
        xml = """
        <Component name="Notifier">
            <Component name="on_event" output="true">
                <Input name="message" type="str" />
                <TestPrint text="Notification: {message}" />
            </Component>
        </Component>

        <Component name="Worker">
            <Input name="on_done_callback" type="component" />
            <Component name="do_work" output="true">
                <TestPrint text="Working..." />
                <on_done_callback message="Job Finished!" />
            </Component>
        </Component>

        <Component name="App">
            <Notifier name="myNotifier" />
            <Worker name="myWorker" on_done_callback={myNotifier.on_event} />
            <myWorker.do_work />
        </Component>
        <App />
        """
        expected = textwrap.dedent("""
        Working...
        Notification: Job Finished!
        """).strip()
        self.assertEqual(self.run_oml(xml).strip(), expected)

    def test_filesystem_composite_structure(self):
        """
        SCENARIO: File System Tree.
        A 'Folder' can contain 'File' objects and other 'Folder' objects.
        Both have a method 'Describe' and a property 'totalSize'.
        
        GOAL: Verify that we can transparently treat a single file 
        and a whole folder the same way (Polymorphism).
        """
        xml = """
        <Component name="File">
            <Input name="title" type="str" />
            <Input name="size" type="int" />
            <Output name="totalSize" set={size} />
            
            <Component name="Describe" output="true">
                <TestPrint text="- {title} ({size} bytes)" />
            </Component>
        </Component>

        <Component name="Folder">
            <Input name="title" type="str" />
            <Input name="ItemsInput" type="component" children="true" />
            <ItemsInput>
                <Local name="items" set={component_calls()} />
            </ItemsInput>

            <Output name="totalSize" set={sum([it.totalSize for it in items])} />

            <Component name="Describe" output="true">
                <TestPrint text="+ Folder: {title} [total: {totalSize} bytes]" />
                <Repeat to={len(items) - 1}>
                    <Local name="it" set={items[i]} />
                    <it.Describe />
                </Repeat>
            </Component>
        </Component>

        <Component name="App">
            <Folder name="root" title="Root">
                <File title="config.sys" size={100} />
                <Folder title="Logs">
                    <File title="error.log" size={250} />
                    <File title="access.log" size={150} />
                </Folder>
                <File title="data.db" size={500} />
            </Folder>

            <TestPrint text="--- Full System Report ---" />
            <root.Describe />
            <TestPrint text="--- End of Report ---" />
        </Component>
        <App />
        """
        # Expected calculation: 100 + (250 + 150) + 500 = 1000
        expected = textwrap.dedent("""
        --- Full System Report ---
        + Folder: Root [total: 1000 bytes]
        - config.sys (100 bytes)
        + Folder: Logs [total: 400 bytes]
        - error.log (250 bytes)
        - access.log (150 bytes)
        - data.db (500 bytes)
        --- End of Report ---
        """).strip()
        
        self.assertMultiLineEqual(self.run_oml(xml), expected)

    def test_component_subtraction_via_inputs(self):
        """
        Verifies that a 'Subtract' component can receive two other 
        components as inputs and compute the difference of their properties.
        """
        xml = """
        <Component name="Subtract">
            <Input name="OperandsInput" type="component" children="true" />
            <OperandsInput>
                <Assert condition={len(component_calls()) == 2} />
                <Local name="comp1" set={component_calls()[0]} />
                <Local name="comp2" set={component_calls()[1]} />
            </OperandsInput>
            <Output name="size" set={comp1.size - comp2.size} />
        </Component>

        <Component name="Shape">
            <Input name="size" type="float" default={0} />
            <Output name="size" set={size} />
        </Component>

        <Component name="App">
            <Subtract name="sub">
                <Subtract>
                    <Shape size={100} />
                    <Shape size={30} />
                </Subtract>
                <Shape size={20} />
            </Subtract>
            <sub>
                <TestPrint text="Subtraction result: {size}" />
            </sub>
        </Component>

        <App />
        """
        expected = "Subtraction result: 50.0"
        
        self.assertEqual(self.run_oml(xml).strip(), expected)

if __name__ == '__main__':
    unittest.main(exit=False)