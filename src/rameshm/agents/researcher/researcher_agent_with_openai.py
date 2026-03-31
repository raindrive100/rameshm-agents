from agents import Agent, Runner, trace, Tool, ModelSettings, input_guardrail, \
    GuardrailFunctionOutput, function_tool, RunResult, handoff
from agents.handoffs import handoff
from agents.mcp import MCPServerStdio
from mcp.server import FastMCP
from agents.tool import WebSearchTool
from pydantic import BaseModel, Field
from IPython.display import display, Markdown
import asyncio
import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from rameshm.agents.utils import basic_setup as rrm_setup
from rameshm.agents.researcher import guardrails as rrm_guardrails
from rameshm.agents.researcher import instructions_config as rrm_instructions_cfg

import importlib

# Run this line to force module updates
importlib.reload(rrm_setup)
importlib.reload(rrm_guardrails)
importlib.reload(rrm_instructions_cfg)

# Set the basic environment.
load_dotenv(dotenv_path=os.getenv("KEY_FILE_PATH"), override=True)  # Load environment variables from .env file
logger = rrm_setup.get_basic_logger(log_level_app=logging.DEBUG)
#rrm_setup.set_required_path_env()

LLM_MODEL = "gpt-4o-mini"

# Set-up Input Guardrail.
improper_query_guardrail = rrm_guardrails.BasicInputGuardrail().create_improper_query_guardrail()

# Create two MCP Servers: brave_search and fetch server
brave_env = {"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")}
researcher_mcp_server_params = [
    {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-brave-search"], "env": brave_env},
    {"command": "uvx", "args": ["mcp-server-fetch"]}
]
researcher_mcp_servers = [MCPServerStdio(params=param, client_session_timeout_seconds=90) for param in researcher_mcp_server_params]

async def safe_server_cleanup(rsrchr_mcp_servers):
    """Safely cleanup MCP servers with proper error handling"""
    for server in rsrchr_mcp_servers:
        try:
            logger.debug(f"Closing Server: {server}.....")
            await server.cleanup()
            logger.debug(f"Closed MCP Server: {server}")
        except Exception as e:
            logger.error(f"Warning: Error during server cleanup (this is usually harmless): {e}")
            # The servers are likely still cleaned up properly despite the error

summarizer_agent = Agent(
    name="Research Summarizer",
    model=LLM_MODEL,
    instructions=rrm_instructions_cfg.summarizer_agent_instructions,
    handoff_description=rrm_instructions_cfg.summarizer_agent_handoff_instructions,
)

class SynthesisInput(BaseModel):
    topic: str = Field(description="Question asked by the user")
    source: list[str] = Field(description="List of URLs used")
    raw_notes: str = Field(description="All raw collected text")

async def log_handoff(ctx, input_data=None):
    # Dummy method to print message that handoff is invoked.
    logger.debug("[on_handoff] -> Research Summarizer called ........")
        #list(input_data.dict().keys()) if input_data else None)
    return ctx

summarizer_handoff = handoff(
    agent=summarizer_agent,
    tool_name_override="transfer_to_research_summarizer",
    tool_description_override=rrm_instructions_cfg.summarizer_agent_handoff_instructions,
    on_handoff=log_handoff,
    input_type=SynthesisInput,
    #input_type=.....,  #optional:enforce a schema for the summarizer
    #input_filter=....  #optional: trim/readact context sent to the summarizer
)

async def get_researcher(rsrchr_mcp_servers) -> Agent:
    instructions = rrm_instructions_cfg.researcher_agent_instructions
    researcher_agent = Agent(
        name="Financial Researcher",
        instructions=instructions, #rrm_instructions_config.researcher_agent_instruction,
        model=LLM_MODEL,
        mcp_servers=rsrchr_mcp_servers,
        input_guardrails=[improper_query_guardrail],
        handoffs=[summarizer_handoff]        
        #handoffs=[summarizer_agent]
    )
    return researcher_agent

# async def get_researcher_tool(researcher_mcp_servers) -> Tool:
#     researcher = await get_researcher(researcher_mcp_servers)
#     return researcher.as_tool(
#         tool_name="Financial Researcher Tool",
#         tool_description="This tool researches online for news and opportunities, \
#                 either based on your specific request to look into a certain stock, \
#                 or generally for notable financial news and opportunities. \
#                 Describe what kind of research you're looking for."
#         )

# Invoke the researcher tool
async def invoke_researcher(rsrchr_mcp_servers, user_query: str) -> RunResult:
    # Start the MCP servers
    for server in researcher_mcp_servers:
        await server.connect()
    try:
        researcher = await get_researcher(rsrchr_mcp_servers)
        with trace("Financial Researcher Agents"):
            result = await Runner.run(researcher, input=user_query)
        return result
    finally:
        # TO DO: Due to some issues with async the below is causing irrecoverable exception. Need to revisit.
        # Commenting out for now.
        #await safe_server_cleanup(rsrchr_mcp_servers)        
        logger.debug("Finished invoke_researcher")
    

if __name__ == "__main__":
    try:
        result = asyncio.run(invoke_researcher(researcher_mcp_servers, 
        "What are the top well known AI Companies and which are the new ones that are coming up and look promising?",)
        )
    except Exception as e:
        logger.error("Exception occurred", exc_info=False)
    # print(dir(result))
    # print(f"Last Agent: {result.last_agent}")
    # print(f"Agent Input: {result.input}")
    print(result.final_output)
    #Write to file
    #result_file_nm = "/home/ramesh/tmp/researcher.md"
    #with open(result_file_nm, mode="w") as f:
    #    f.write(result.final_output)

