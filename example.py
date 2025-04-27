# /// script
# dependencies = [
#   "temporalio-server", # The server wrapper/context manager
#   "temporalio>=1.0.0", # The SDK itself
# ]
# ///

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from temporalio_server import DevServer

TASK_QUEUE_NAME = "my-task-queue"
WORKFLOW_ID = "my-workflow-id"


@activity.defn
def say_hello(name: str) -> str:
    return f"Hello, {name}!"


@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say_hello,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )


async def main():
    async with DevServer() as server:
        client = await Client.connect(server.target)
        async with Worker(
            client,
            task_queue=TASK_QUEUE_NAME,
            workflows=[GreetingWorkflow],
            activities=[say_hello],
            activity_executor=ThreadPoolExecutor(),
        ):
            result = await client.execute_workflow(
                GreetingWorkflow.run,
                "Temporal",
                id=WORKFLOW_ID,
                task_queue=TASK_QUEUE_NAME,
            )
            print(f"Workflow Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
