"""
Demonstrates the use of tools leveraging chat models. No agents are used in this example.
It also shows structured output using OpenAI.
"""
import logging

from dotenv import load_dotenv
import os
import json
from typing import Tuple
from logging import getLogger
from pypdf import PdfReader
import gradio as gr
from openai import OpenAI
from pydantic import BaseModel

# Set up logging
log_format =  "%(asctime)s - %(process)d - %(name)s - %(filename)s - %(funcName)s - %(lineno)d \
- %(levelname)s - %(message)s"
logging.basicConfig(format=log_format)
logger = getLogger(__name__)

load_dotenv(dotenv_path = os.getenv("KEY_FILE_PATH"), override=True)
print(f"OPENAI_API_KEY is set: {os.getenv('OPENAI_API_KEY')[:10]}")

llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
file_contents = ""

# Define a Pydantic model for the structured output
class QuestionAnswer(BaseModel):
    user_question: str
    ai_answer: str

# Create a function to record any user question that the model couldn't answer
def record_unanswered_question(question: str):
    """Record the unanswered question"""
    print(f"\nUnanswered question: {question}\n")
    return {"role": "assistant",
            "content": "I don't know the answer to that question based on the provided document."
    }

record_unanswered_question_json = {
    "name": "record_unanswered_question",
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
    {"type": "function", "function": record_unanswered_question_json}
]

def handle_tool_calls(tool_calls: list[dict]) -> list[dict]:
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
        text = page.extract_text()
        contents += text if text else ""

    return contents

def gr_file_handler(file_path: str) -> str:
    """Invoked by Gradio front end for PDF Files. Returns empty string so that
    """
    global file_contents
    if file_path and file_path.lower().endswith(".pdf"):
        file_contents = pdf_file_handler(file_path)
    else:
        print(f"File {file_path} is not a PDF file.")
        raise ValueError("Only PDF files are supported.")
    return

system_prompt = "You are a helpful AI assistant. You will be provided with the contents of a PDF document. \
                Only use the information in the document to answer the user's questions. \
                If you don't know the answer, don't make up an answer and invoke the relevant tool to answer the user's questions. \
                Always answer in a structured format as per the Pydantic model provided."

def gr_chat_handler(user_question: str, chat_history: list[dict[str, str]]) -> Tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Invoked by Gradio front end for chat messages. Returns the model's response."""
    global file_contents

    done = False
    try:
        if not file_contents:
            raise ValueError("No document content available. Please upload a PDF document first.")
        while not done:
            if len(chat_history) == 0:
                # First message from the user. Add the document content to the system prompt
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"The document content is as follows: {file_contents}"},
                ]
            chat_history.append({"role": "user", "content": user_question})
            messages = chat_history.copy()
            response = llm_client.responses.parse(
                model="gpt-4o-mini",
                input=messages,
                tools=tools,
                text_format=QuestionAnswer
            )

            finish_reason = response.choices[0].finish_reason
            if finish_reason == "tool_call":
                message = response.choices[0].message
                tool_calls = response.choices[0].tool_calls
                tool_responses = handle_tool_calls(tool_calls)
                messages.append(message)
                messages.extend(tool_responses)
            else:
                done = True
                answer: QuestionAnswer = response.output_parsed
                chat_history.append({"role": "assistant",
                                     "content": answer.ai_answer}
                                    )
        return chat_history, chat_history
    except Exception as e:
        error_response = [
            {"role": "assistant", "content": f"🔥 Please correct the following error and resubmit. ERROR: {str(e)}\n\n "}
        ]
        updated_history = chat_history + error_response if len(chat_history) else error_response
        logger.error(error_response, exc_info=True,)
        # Return: chat_history maintain the chat state for system. The updated_history is for UI display
        return chat_history, updated_history


with gr.Blocks() as demo:
    ui_chat_history = gr.State([])    # Maintain state for chat history

    gr.Markdown(
        """
        # Basic Tool Example with Chat Models
        This example demonstrates the use of tools with chat models. No agents are used in this example.
        It also shows structured output using Pydantic models.
        - Upload a PDF document.
        - Ask questions based on the document content.
        - If the model doesn't know the answer, it will invoke a tool to record the unanswered question.
        - If the model answers the question, it will invoke a tool to record the user question and AI answer.
        """
    )
    with gr.Row():
        with gr.Column(scale=1):
            pdf_file = gr.File(label="Upload PDF Document", file_types=['.pdf'], type="filepath")
            pdf_file.change(fn=gr_file_handler, inputs=pdf_file, outputs=[])
        with gr.Column(scale=3):
            chat_box = gr.Chatbot(label="Chat about the document", height=400, type="messages")
            user_input = gr.Textbox(label="Your Question", placeholder="Ask a question about the document...")
            user_input.submit(fn=gr_chat_handler,
                              inputs=[user_input, ui_chat_history],
                              outputs=[ui_chat_history, chat_box]
                              )

    gr.Examples(
        examples=[
            ["What is the main topic of the document?"],
            ["Can you summarize the key points?"],
            ["What are the conclusions drawn in the document?"],
            ["Who is the author of the document?"],
            ["What data or evidence is presented?"],
            ["Are there any recommendations made?"],
            ["What is the publication date of the document?"],
            ["Can you explain a specific section or term used in the document?"]
        ],
        inputs=user_input
    )

if __name__ == "__main__":
    demo.launch()