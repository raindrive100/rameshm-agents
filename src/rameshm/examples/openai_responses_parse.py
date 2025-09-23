"""Example of using tools with structured output and tools using openai.responses.parse."""
from openai import OpenAI, pydantic_function_tool
from pydantic import BaseModel

client = OpenAI()

# Schema for final structured answer
class FinalAnswer(BaseModel):
    answer: str = Field(description="The Model answer to the user question")
    confidence: float

# Tool definition
class RecordUnansweredQuestion(BaseModel):
    question: str = Field(description="The question asked by the user that the model could not answer")

record_tool = pydantic_function_tool(
    RecordUnansweredQuestion,
    name="record_unanswered_question",
    description="Use this tool to record the unanswered question"
)

response = client.responses.parse(
    model="gpt-4.1",
    input="What is the capital of France?",
    tools=[record_tool],
    schema=FinalAnswer   # ✅ not response_format here!
)

print(response.output_parsed)  # -> FinalAnswer(answer="Paris", confidence=0.95)
