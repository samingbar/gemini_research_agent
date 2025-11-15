from typing import List
from datetime import timedelta

from temporalio import workflow

from ...resources.custom_types.types import (
    AgentInput,
    AgentStepInput,
    AgentStepOutput,
    ToolCall,
)
from ...resources.myprompts.history import PromptHistory
from ...resources.myprompts.models import SystemPrompt, TaskPrompt, BasePrompt
from ...resources.myprompts.provider import LLMProvider
from ...resources.prompts.prompts import SYSTEM_PROMPT, MANAGED_AGENT_TASK


@workflow.defn
class AgentLoopWorkflow:
    def __init__(self):
        self.history: PromptHistory = PromptHistory()
        self.tools_used: List[str] = []
        self.step_counter: int = 0
        self.max_steps: int = 30

    @workflow.run
    async def run(self, input: AgentInput) -> str:
        """
        Main loop:
        - Build initial prompts from the task
        - Call LLM step activity
        - Optionally invoke a tool
        - Repeat until final answer or max_steps
        """

        # Build initial prompt history using the prompt models
        system_prompt = SystemPrompt(text=SYSTEM_PROMPT.strip())
        task_text = MANAGED_AGENT_TASK.format(task_description=input.task).strip()
        task_prompt = TaskPrompt(text=task_text)

        self.history.add(system_prompt)
        self.history.add(task_prompt)

        # Assemble into provider-specific messages for Gemini
        history_messages = self.history.to_messages(provider=LLMProvider.GEMINI)

        next_input = AgentStepInput(task=input.task, history=history_messages)

        last_output: AgentStepOutput | None = None

        for step in range(1, self.max_steps + 1):
            self.step_counter = step

            # ----- Step 1: Ask LLM what to do next -----
            llm_result = await workflow.execute_activity(
                "llm_step_activity",
                next_input,
                schedule_to_close_timeout=timedelta(seconds=90),
            )

            # Temporal + data converter may deserialize to dict; normalize.
            if isinstance(llm_result, dict):
                llm_result = AgentStepOutput(**llm_result)

            last_output = llm_result

            # Record assistant message if present
            if llm_result.output_text:
                assistant_prompt = BasePrompt(role="assistant", text=llm_result.output_text)
                self.history.add(assistant_prompt)
                history_messages = self.history.to_messages(provider=LLMProvider.GEMINI)

            # ----- Step 2: Check if workflow is finished -----
            if llm_result.is_final:
                workflow.logger.info("Agent finished.")
                return llm_result.output_text or ""

            # ----- Step 3: If tool call requested -----
            if llm_result.tool_call is not None:
                tool_req: ToolCall = llm_result.tool_call
                self.tools_used.append(tool_req.name)

                tool_result: str = await workflow.execute_activity(
                    "tool_activity",
                    tool_req,
                    schedule_to_close_timeout=timedelta(seconds=30),
                )

                # Add tool result to history as a tool message
                tool_prompt = BasePrompt(role="tool", text=tool_result)
                self.history.add(tool_prompt)
                history_messages = self.history.to_messages(provider=LLMProvider.GEMINI)

                # Send updated history back to the LLM
                next_input = AgentStepInput(task=input.task, history=history_messages)
                continue

            # If not final and no tool call, continue with updated history
            next_input = AgentStepInput(task=input.task, history=history_messages)

        # Max steps reached
        workflow.logger.info("Max steps reached without final answer.")
        if last_output and last_output.output_text:
            return last_output.output_text
        return ""
