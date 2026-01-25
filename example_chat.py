from openai import OpenAI
import json

class LLM:
    
    def __init__(self, api_key: str, model_name: str, base_url: str, sys_prompt: str):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        self.tool_use_system_prompt = (
            "You can use tools to help you to solve tasks."
            "When you detect that a tool is needed, respond with a JSON object AT THE LAST LINE OF YOUR RESPONSE specifying the tool name and its input. Then, you will receive the tool's output in the next user message. You don't need to answer on your own."
            "The available tools are: "
            "1. bash: for executing bash commands."
            "2. calculator: for performing mathematical calculations."
            "Format your response as: "
            '{"tool": "tool_name", "input": "input_for_tool"}'
            "For example: "
            '{"tool": "calculator", "input": "2 + 2"}'
        )
        full_sys_prompt = sys_prompt + "\n" + self.tool_use_system_prompt
        self.chat_history = [
            {"role": "system", "content": full_sys_prompt}
        ]
        
    def chat(self, user_input: str) -> str:
        self.chat_history.append({"role": "user", "content": user_input})
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.chat_history,
            stream=False
        )
        
        assistant_message = response.choices[0].message.content
        self.chat_history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message, self.detect_tool_use(assistant_message)
    
    def detect_tool_use(self, assistant_message: str) -> dict:
        try:
            tool_use = json.loads(assistant_message.split('\n')[-1])
            if "tool" in tool_use and "input" in tool_use:
                return (tool_use["tool"], tool_use["input"])
        except json.JSONDecodeError:
            pass
        return (None, None)
    
if __name__ == "__main__":
    llm = LLM(
        api_key=open('/home/zhh/看你妈呢').read().strip(),
        model_name="deepseek-chat",
        base_url="https://api.deepseek.com",
        sys_prompt="You are a helpful assistant, ready to use tools when necessary."
    )
    
    # user_input = "What is 555225 plus 771209?"
    user_input = "List the files in the current directory."
    response, tool_use = llm.chat(user_input)
    print("Assistant Response:", response)
    if tool_use[0]:
        print("Tool Detected:", tool_use)