from openai import OpenAI, pydantic_function_tool
from pydantic import BaseModel, Field

client = OpenAI()

# Example Pydantic schema for final output
class FinalAnswer(BaseModel):
    answer: str = Field(description="The Model answer to the user question")
    confidence: float

# Define a tool (via pydantic_function_tool)
class RecordUnansweredQuestion(BaseModel):
    question: str = Field(description="The question asked by the user that the model could not answer")

record_tool = pydantic_function_tool(
    RecordUnansweredQuestion,
    name="record_unanswered_question",
    description="Use this tool to record the unanswered question"
)

response = client.responses.create(
    model="gpt-4.1",
    input="What is the capital of France?",
    tools=[record_tool],
    response_format={
        "type": "json_schema",
        "json_schema": FinalAnswer.model_json_schema()
    }
)

print(response.output[0].content[0].text)  # JSON string {"answer": "...", "confidence": ...}
