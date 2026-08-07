from app.services.llm import generate_response, generate_chat_response, generate_chat_response_stream


async def chat(prompt: str):
    return await generate_response(prompt)


async def structured_chat(contents: list[dict], system_instruction: str):
    return await generate_chat_response(contents, system_instruction)


def structured_chat_stream(contents: list[dict], system_instruction: str):
    return generate_chat_response_stream(contents, system_instruction)