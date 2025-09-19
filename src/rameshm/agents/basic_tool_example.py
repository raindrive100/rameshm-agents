"""
Demonstrates the use of tools leveraging chat models. No agents are used in this example.
It also shows structured output using OpenAI.
"""
from dotenv import load_dotenv
import os
import json
from pypdf import PdfReader
import gradio as gr
from openai import OpenAI
from pydantic import BaseModel

load_dotenv(override=True) # override the environment variables if exist


# Define a Pydantic model for the structured output
class _QuestionAnswer(BaseModel):
    user_question: str
    ai_answer: str

# Create functions to record any user questions that are sent to the model
def record_user_question_answer(question: str, ai_answer: str):
    """Record the user question"""
    print(f"\nUser question: {question} and AI answer: {ai_answer}\n")
    return {"recorded": "ok"}

# Create a function to record any user question that the model couldn't answer
def record_unaswered_question(question: str):
    """Record the unanswered question"""
    print(f"\nUnanswered question: {question}\n")
    return {"recorded": "ok"}


record_user_question_answer_json = {
    "name": "record_user_question_answer",
    "description": "Use this tool to record the user question and AI answer",
    "parameters": {
        "type": "object",
        "properties": {
            "user_question": {"type": "string",
                              "description": "The question asked by the user"},
            "ai_answer": {"type": "string",
                          "description": "The answer given by the AI"}
        },
        "required": ["user_question", "ai_answer"],
        "additionalProperties": False
    }
}

record_unaswered_question_json = {
    "name": "record_unaswered_question",
    "description": "Use this tool to record the unanswered question",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string",
                          "description": "The question asked by the user"}
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [
    {"type": "function", "function": record_user_question_answer_json},
    {"type": "function", "function": record_unaswered_question_json}
]

def handle_tool_calls(tool_calls: list[dict]) -> list[str]:
    """Handle the tool calls"""
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = tool_call.function.arguments
        tool_id = tool_call.id
        print(f"\nTool Called: {tool_name}, flush=True")
        tool = globals().get(tool_name)
        result = tool(**tool_args) if tool else {}
        results.append({
            "role": "tool",
            "content": json.dumps(result),
            "tool_call_id": tool_id
        })
        return results

def pdf_file_handler(file_path: str) -> str:
    """Taken file path for a PDF file and returns its contents as string"""
    reader = PdfReader(file_path)
    contents = ""
    for page in reader.pages:
        text = page.extract_text
        if text:
            contents += text
    return contents
    


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create a function to generate a response using the model
def generate_response(question: str):
    """Generate a response using the model"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": question}],
        tools=tools
    )
    return response.choices[0].message.content