import asyncio
import uuid
from pprint import PrettyPrinter

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from ...resources.custom_types.types import AgentInput
from .workflow import AgentLoopWorkflow
from .config import TASK_QUEUE, ADDRESS

pp = PrettyPrinter(indent=1, width=120)


async def main(prompt:str = "Temporal") -> str:
    interrupt_event = asyncio.Event()
    client = await Client.connect(
        ADDRESS,
        data_converter=pydantic_data_converter,    
    )

    handle = await client.start_workflow(
        AgentLoopWorkflow.run,
        AgentInput(task=prompt),
        id = f"durable-test-id-{uuid.uuid4()}",
        task_queue = TASK_QUEUE
    )

    try:
        result = await handle.result()
        pp.pprint(result)
    except Exception as exc:
        print(f"Workflow finished with exception: {exc}")

if __name__ == "__main__":
    asyncio.run(main())
