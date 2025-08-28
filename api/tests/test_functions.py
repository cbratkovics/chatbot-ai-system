import pytest

from api.services.functions.base import function_registry
from api.services.functions.calculator import CalculatorFunction, DataAnalysisFunction
from api.services.functions.init_functions import initialize_functions


@pytest.mark.asyncio
async def test_calculator_function():
    calc = CalculatorFunction()

    # Test basic operations
    result = await calc.execute(expression="2 + 2")
    assert result == 4

    result = await calc.execute(expression="10 * 5")
    assert result == 50

    result = await calc.execute(expression="sqrt(16)")
    assert result == 4

    result = await calc.execute(expression="sin(pi/2)")
    assert abs(result - 1.0) < 0.0001


@pytest.mark.asyncio
async def test_data_analysis_function():
    analyzer = DataAnalysisFunction()

    data = [1, 2, 3, 4, 5]

    # Test mean
    result = await analyzer.execute(data=data, operation="mean")
    assert result["result"] == 3.0

    # Test sum
    result = await analyzer.execute(data=data, operation="sum")
    assert result["result"] == 15


def test_function_registry():
    initialize_functions()

    # Check functions are registered
    assert len(function_registry._functions) >= 4

    # Check OpenAI schema generation
    schemas = function_registry.get_all_schemas()
    assert len(schemas) >= 4

    # Check calculator schema
    calc_schema = next(s for s in schemas if s["name"] == "calculator")
    assert "expression" in calc_schema["parameters"]["properties"]


@pytest.mark.asyncio
async def test_function_execution():
    initialize_functions()

    # Test calculator through registry
    result = await function_registry.execute_function("calculator", {"expression": "2 + 2"})
    assert result.result == 4
    assert result.error is None
