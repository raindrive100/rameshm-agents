from agents import Agent, ModelSettings, Runner, trace, input_guardrail, GuardrailFunctionOutput
from pydantic import BaseModel, Field
import os
from typing import Any
from rameshm.agents.utils import basic_setup as rrm_setup

logger = rrm_setup.get_basic_logger()

class CheckInput(BaseModel):
    is_appropriate: bool = Field(description="True if the input is appropriate, False otherwise.")
    user_input: str = Field(description="The user's input that was checked.")
    inappropriate_reason: str = Field(
        description="The reason why the input was deemed inappropriate, empty if appropriate.")

# Create an input guardrail agent to ensure the user's input is appropriate for a professional environment.
class BasicInputGuardrail():
    def __init__(self, llm_model: str = "gpt-4o-mini", model_settings: dict[str, Any] = {}):
        self.llm_model = llm_model
        self.instructions = self.get_input_guardrail_instructions()
        self.model_settings = model_settings or {}
        self.agent = self.get_input_guardrail_agent()
        

    def get_input_guardrail_instructions(self) -> str:
        return (
            "You are an input guardrail agent. User's input should be appropriate for professional environment. "
            "Your task is to ensure that the user's input is appropriate "
            "and does not contain any harmful or unprofessional or inappropriate content."
            "If the input is appropriate, respond with 'APPROPRIATE'. If the input is inappropriate, respond with 'INAPPROPRIATE'."
        )
    
    def get_input_guardrail_agent(self) -> Agent:
        input_guardrail_agent = Agent(
            name="Input Guardrail Agent",
            instructions=self.instructions,
            model=self.llm_model,
            model_settings=ModelSettings(**self.model_settings),
            output_type=CheckInput,
        )
        return input_guardrail_agent

    def create_improper_query_guardrail(self) -> GuardrailFunctionOutput:
        """ Returns a guard rail funtion that the calling agents can use """
        @input_guardrail
        async def improper_user_query_guardrail(ctx, agent, message: str) -> GuardrailFunctionOutput:
            # Check if any unprofessions words are used in the query
            # We can add more checks like: Checking for message length, any PI data etc..
            result = await Runner.run(self.agent, input=message, context=ctx)
            logger.debug(result.final_output)
            if result.final_output.is_appropriate:
                reason = "Input is appropriate"
                tripwire = False
            else:
                reason = f"Inappropriate input detected. Reason: {result.final_output.inappropriate_reason}"
                tripwire = True
            return GuardrailFunctionOutput(
                output_info={"reason": reason},
                tripwire_triggered=tripwire,
            )
        return improper_user_query_guardrail
