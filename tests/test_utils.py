"""
Test utility tools.

This module provides test tools:
1. python_exec: Execute Python code
2. file_write: Write content to a file
3. file_search: Search for files matching a pattern
4. get_weather: Get weather information for a city (mock)
5. get_temperature: Get temperature for a city (mock)
"""

import os
import sys
import subprocess
import glob
from io import StringIO
from typing import List


def python_exec(code: str) -> str:
    """
    Execute Python code and return the output.

    Args:
        code: Python code to execute

    Returns:
        The stdout output from the code execution
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        # Execute the code
        exec(code, {})

        # Get the output
        output = sys.stdout.getvalue()
        return output if output else "Code executed successfully (no output)"

    except Exception as e:
        return f"Error: {str(e)}"

    finally:
        # Restore stdout
        sys.stdout = old_stdout


def file_write(path: str, content: str) -> str:
    """
    Write content to a file.

    Args:
        path: Path to the file to write
        content: Content to write to the file

    Returns:
        Confirmation message
    """
    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Write the file
        with open(path, "w") as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to {path}"

    except Exception as e:
        return f"Error writing file: {str(e)}"


def file_search(pattern: str, directory: str = ".") -> str:
    """
    Search for files matching a glob pattern.

    Args:
        pattern: Glob pattern to match (e.g., "*.py", "**/*.txt")
        directory: Directory to search in (default: current directory)

    Returns:
        JSON string containing list of matching file paths
    """
    try:
        # Use glob to find matching files
        search_pattern = os.path.join(directory, pattern)
        matches = glob.glob(search_pattern, recursive=True)

        # Return as formatted string
        if matches:
            return f"Found {len(matches)} files:\n" + "\n".join(matches)
        else:
            return "No files found matching the pattern"

    except Exception as e:
        return f"Error searching files: {str(e)}"


def get_weather(city: str) -> str:
    """
    Get weather information for a city (mock implementation).

    Args:
        city: Name of the city

    Returns:
        Weather description including condition and temperature
    """
    # Mock weather database
    weather_db = {
        "London": "Cloudy with light rain, 15°C",
        "New York": "Sunny and clear, 22°C",
        "Tokyo": "Rainy, 18°C",
        "Beijing": "Clear skies, 20°C",
        "Shanghai": "Partly cloudy, 23°C",
        "Paris": "Overcast, 16°C",
        "Berlin": "Cold and windy, 10°C",
        "Sydney": "Hot and sunny, 28°C",
    }

    weather = weather_db.get(city, f"Weather data not available for {city}")
    return weather


def get_temperature(city: str) -> str:
    """
    Get the current temperature for a city (mock implementation).

    Args:
        city: Name of the city

    Returns:
        Temperature in Celsius
    """
    # Mock temperature database
    temp_db = {
        "London": "15°C",
        "New York": "22°C",
        "Tokyo": "18°C",
        "Beijing": "20°C",
        "Shanghai": "23°C",
        "Paris": "16°C",
        "Berlin": "10°C",
        "Sydney": "28°C",
    }

    temp = temp_db.get(city, f"Temperature data not available for {city}")
    return temp
