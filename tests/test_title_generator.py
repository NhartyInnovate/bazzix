import unittest
import asyncio
from app.services.title_generator import dispatch_background_title, _bg_tasks


class TestTitleGenerator(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_background_title(self):
        # Ensure registry is clear before test
        _bg_tasks.clear()
        self.assertEqual(len(_bg_tasks), 0)

        # Dispatching should add a task to the registry
        dispatch_background_title(1, "Hello world")

        # Task should be in the registry
        self.assertEqual(len(_bg_tasks), 1)

        task = next(iter(_bg_tasks))
        self.assertFalse(task.done())

        # Await the task to finish (it will fail because DB is not mocked, but the callback should still fire)
        try:
            await task
        except Exception:
            pass

        # Give the done_callback a tick to execute
        await asyncio.sleep(0.01)

        # Task should be removed from the registry
        self.assertEqual(len(_bg_tasks), 0)
