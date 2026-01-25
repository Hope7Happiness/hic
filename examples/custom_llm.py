"""
Example demonstrating how to create a custom LLM implementation.

This example shows:
1. How to extend the LLM abstract base class
2. Creating a mock LLM for testing
3. Using the custom LLM with agents
"""

from typing import Optional, List
from agent import LLM, Tool, Agent


class MockLLM(LLM):
    """
    A mock LLM that returns predefined responses.

    Useful for testing and development without API costs.
    """

    def __init__(self, responses: List[str]):
        """
        Initialize the mock LLM.

        Args:
            responses: List of predefined responses to return
        """
        super().__init__()
        self.responses = responses
        self.call_count = 0

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Return a predefined response.

        Args:
            prompt: User message
            system_prompt: Optional system prompt

        Returns:
            Next predefined response
        """
        # Add system prompt if this is the first message
        if not self.history and system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

        # Add user message
        self.history.append({"role": "user", "content": prompt})

        # Get next response
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
        else:
            response = "No more responses available"

        # Add assistant message
        self.history.append({"role": "assistant", "content": response})

        return response


def calculator(expression: str) -> float:
    """Evaluate a mathematical expression."""
    try:
        return float(eval(expression))
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    """Run the example."""

    print("=" * 60)
    print("Custom LLM Implementation Example")
    print("=" * 60)
    print()

    # Create a mock LLM with predefined responses
    mock_responses = [
        # First response: use the calculator tool
        """Thought: I need to calculate 10 + 5
Action: tool
Tool: calculator
Arguments: {"expression": "10 + 5"}""",
        # Second response: finish with the result
        """Thought: The calculation is complete
Action: finish
Response: The result of 10 + 5 is 15.0""",
    ]

    llm = MockLLM(responses=mock_responses)
    print("Created MockLLM with predefined responses")
    print()

    # Create a tool
    calc_tool = Tool(calculator)
    print(f"Created tool: {calc_tool.name}")
    print()

    # Create agent with mock LLM
    agent = Agent(llm=llm, tools=[calc_tool], max_iterations=5, name="MockAgent")
    print("Created agent with MockLLM")
    print()

    # Run the agent
    print("Running agent with task: 'Calculate 10 + 5'")
    print()
    response = agent.run("Calculate 10 + 5", verbose=True)

    # Display results
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Success: {response.success}")
    print(f"Iterations: {response.iterations}")
    print(f"Response: {response.content}")
    print()

    # Show conversation history
    print("=" * 60)
    print("CONVERSATION HISTORY")
    print("=" * 60)
    for i, msg in enumerate(llm.get_history(), 1):
        print(f"{i}. {msg['role'].upper()}: {msg['content'][:100]}...")
        print()


if __name__ == "__main__":
    main()
