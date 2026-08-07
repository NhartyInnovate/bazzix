import asyncio
from openai import AsyncOpenAI

from app.core.config import settings

# If no API key is provided, we run in Mock mode for testing purposes
if settings.OPENAI_API_KEY:
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY
    )
else:
    client = None


async def generate_response(prompt: str) -> str:
    if client is None:
        if "title" in prompt.lower() or "generate a very short conversation title" in prompt.lower():
            return "Mock Workspace Session"
        return f"This is a mock AI response. (Bazzix running in Mock Mode - OPENAI_API_KEY not configured).\n\nYou said: {prompt[:100]}..."

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content or ""

    except Exception as e:
        raise RuntimeError(f"OpenAI API Error: {str(e)}")


async def generate_chat_response(contents: list[dict], system_instruction: str) -> str:
    if client is None:
        last_message = ""
        if contents:
            last_message = contents[-1].get("content", "")
        return f"This is a mock AI response. (Bazzix running in Mock Mode - OPENAI_API_KEY not configured).\n\nYou said: {last_message[:100]}..."

    try:
        messages = [
            {"role": "system", "content": system_instruction}
        ] + contents

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
        )

        return response.choices[0].message.content or ""

    except Exception as e:
        raise RuntimeError(f"OpenAI API Error: {str(e)}")


async def generate_chat_response_stream(contents: list[dict], system_instruction: str):
    if client is None:
        last_message = ""
        if contents:
            last_message = contents[-1].get("content", "")
        mock_response = f"This is a mock AI response. (Bazzix running in Mock Mode - OPENAI_API_KEY not configured).\n\nYou said: {last_message[:100]}..."
        
        # Stream mock response with simulated delay
        words = mock_response.split(" ")
        for i, word in enumerate(words):
            yield (word + " ") if i < len(words) - 1 else word
            await asyncio.sleep(0.05)
        return

    try:
        messages = [
            {"role": "system", "content": system_instruction}
        ] + contents

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            stream=True
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
                await asyncio.sleep(0.02)

    except Exception as e:
        raise RuntimeError(f"OpenAI API Error: {str(e)}")