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
from pydantic import BaseModel, Field

# Set up logging
log_format =  "%(asctime)s - %(process)d - %(name)s - %(filename)s - %(funcName)s - %(lineno)d \
- %(levelname)s - %(message)s"
logging.basicConfig(format=log_format)
logger = getLogger(__name__)
logger.setLevel(logging.DEBUG)

load_dotenv(dotenv_path = os.getenv("KEY_FILE_PATH"), override=True)

llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
file_contents = ""

# Define a Pydantic model for the structured output
class QuestionAnswer(BaseModel):
    model_config = {"extra": "forbid"}  # This ensures additionalProperties: false
    user_question: str = Field(description="The question asked by the user")
    ai_answer: str = Field(description="The answer provided by the AI model")

# Create a function to record any user question that the model couldn't answer
def record_unanswered_question(question: str) -> str:
    """Record the unanswered question"""
    logger.debug(f"In record_unanswered_question function. Question: {question}")
    return "Question recorded successfully. I don't know the answer to that question based on the provided document."

record_unanswered_question_tool = {
    "name": "record_unanswered_question",   # This name should match the function name because we use globals() to find the function
    "description": "Use this tool to record user question that the model could not answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Question asked by the user that the model could not answer"}
        },
        "required": ["question"],
        "additionalProperties": False   # This is important to ensure strict schema
    }
}

tools = [
    {"type": "function", "function": record_unanswered_question_tool}
]

def get_tool_call_message(tool_calls: list[dict], message_content) -> dict:
    tool_call_message = {
        "role": "assistant",
        "content": message_content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            } for tc in tool_calls
        ]
    }
    return tool_call_message


def handle_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Handle the tool calls"""
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        tool_id = tool_call.id
        tool = globals().get(tool_name)
        result = tool(**tool_args) if tool else {}
        results.append({
            "role": "tool",
            "content": result,
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

def gr_file_handler(file_path: str):
    """Invoked by Gradio front end for PDF Files. Returns empty string so that
    """
    global file_contents
    if file_path and file_path.lower().endswith(".pdf"):
        file_contents = pdf_file_handler(file_path)
        logger.debug("File read successfully.")
    else:
        print(f"File {file_path} is not a PDF file.")
        raise ValueError("Only PDF files are supported.")

    return

system_prompt = """You are a helpful AI assistant. You will be provided with the contents of a PDF document. 
Only use the information in the PDF document content to answer the user's questions. 
If you don't know the answer based on the PDF document content, use the record_unanswered_question tool.
Always provide your response in a structured format with both the user question and your answer."""

def gr_chat_handler(user_question: str, chat_history: list[dict[str, str]]) -> Tuple[list[dict[str, str]], list[dict[str, str]], str]:
    """Invoked by Gradio front end for chat messages. Returns the model's response."""
    global file_contents

    logger.debug(f"\nUser Question: {user_question}")

    try:
        if not file_contents:
            raise ValueError("No document content available. Please upload a PDF document first.")
        # Build the messages for the chat completion
        if len(chat_history) == 0:
            # First message, include system prompt and document content
            logger.debug("FIRST MESSAGE")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document Content: {file_contents}\n\nUser Question: {user_question}"},
            ]
        else:
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": user_question})

        done = False
        loop_count, max_loops = 0, 3
        while not done and loop_count <= max_loops:  # Prevent infinite loops
            loop_count += 1
            logger.debug(f"Loop {loop_count} of {max_loops}")
            response = llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "question_answer",
                        "schema": QuestionAnswer.model_json_schema(),
                        "strict": True  # Ensures compliance with the schema
                    }
                }
            )
            logger.debug("Completed call to chat.completions.create()")
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "tool_calls" and message.tool_calls:
                logger.debug("Tool being invoked")
                tool_calls = message.tool_calls
                tool_responses = handle_tool_calls(tool_calls)
                tool_call_message = get_tool_call_message(tool_calls, message.content)
                messages.append(tool_call_message)
                messages.extend(tool_responses)
                #print(f"DEBUG Messages after tool calls: {messages}")
            elif finish_reason == "stop":
                logger.debug("Model has provided a final answer")
                done = True
                content = response.choices[0].message.content
                if content:
                    answer_data = json.loads(content)
                    answer = QuestionAnswer(**answer_data)

                    # Update chat history
                    chat_history.append({"role": "user", "content": user_question})
                    chat_history.append({"role": "assistant", "content": answer.ai_answer})
            else:
                raise ValueError(f"Unexpected finish reason: {finish_reason}")

        logger.debug("Successfully completed processing the user question.")
        return chat_history, chat_history, ""   # The last empty string is for the user input box to be cleared
    except Exception as e:
        error_response = {"role": "assistant", "content": f"🔥 Please correct the following error and resubmit. ERROR: {str(e)}\n\n "}
        updated_history = chat_history.append(error_response) if len(chat_history) else [error_response]
        logger.error(error_response, exc_info=True,)

        # Return: chat_history maintains the chat state for system. The updated_history is for UI display
        # The last empty string is for the user input box to be cleared
        return chat_history, updated_history, ""


with gr.Blocks() as demo:
    ui_chat_history = gr.State([])    # Maintain state for chat history

    gr.Markdown(
        """
        # Basic Tool Example with Chat Models
        This example shows how chat models use tools without agents and return structured output via Pydantic models:
        - Upload a PDF document.
        - Ask questions about its content.
        - If the model doesn't know the answer, the model logs it using a tool.
        - If the model knows the answer, answer is displayed in the chat.
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
                              outputs=[ui_chat_history, chat_box, user_input]
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
    demo.launch(show_api=False, share=False)