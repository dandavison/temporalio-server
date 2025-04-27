import asyncio
import logging

# Import ThreadPoolExecutor
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

# Import the DevServer context manager from our package
from temporalio_server import DevServer

# Configure basic logging for the example
logging.basicConfig(level=logging.INFO)

TASK_QUEUE_NAME = "my-task-queue"
WORKFLOW_ID = "my-workflow-id"


# --- Activity Definition ---


@activity.defn
def say_hello(name: str) -> str:
    """A simple activity that returns a greeting."""
    activity.logger.info(f"Running activity with parameter: {name}")
    return f"Hello, {name}!"


# --- Workflow Definition ---


@workflow.defn
class GreetingWorkflow:
    """Workflow that calls the say_hello activity."""

    @workflow.run
    async def run(self, name: str) -> str:
        workflow.logger.info(f"Workflow started with input: {name}")
        # Execute the activity
        result = await workflow.execute_activity(
            say_hello,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )
        workflow.logger.info(f"Workflow completed with result: {result}")
        return result


# --- Main Execution Logic ---


async def main():
    """Starts the DevServer, runs a worker, and executes the workflow."""

    # Start the Temporal development server using the context manager.
    # The server will be automatically stopped when the 'with' block exits.
    logging.info("Starting Temporal development server...")
    async with DevServer(log_level="info") as server:
        logging.info(f"Temporal server started on {server.target}")

        # Connect a Temporal client to the running server
        client = await Client.connect(server.target)
        logging.info("Temporal client connected.")

        # Run a worker process that hosts the workflow and activity.
        # The worker will automatically connect to the server and poll for tasks.
        logging.info(f"Starting worker on task queue: {TASK_QUEUE_NAME}")
        # Create an executor for sync activities
        activity_executor = ThreadPoolExecutor()
        async with Worker(
            client,
            task_queue=TASK_QUEUE_NAME,
            workflows=[GreetingWorkflow],
            activities=[say_hello],
            activity_executor=activity_executor,  # Provide the executor
        ):
            # Worker is running, now we can execute the workflow.
            logging.info(f"Executing workflow: {WORKFLOW_ID}")
            result = await client.execute_workflow(
                GreetingWorkflow.run,
                "Temporal",  # Input to the workflow
                id=WORKFLOW_ID,
                task_queue=TASK_QUEUE_NAME,
            )

            logging.info(f"Workflow execution finished. Result: {result}")

    logging.info("Temporal server has been shut down.")


if __name__ == "__main__":
    logging.info("Running example...")
    asyncio.run(main())
    logging.info("Example finished.")
