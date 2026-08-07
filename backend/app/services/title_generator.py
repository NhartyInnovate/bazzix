from app.services.llm import generate_response


async def generate_title(first_message: str) -> str:
    prompt = f"""
Generate a very short conversation title.

Rules:
- Maximum 5 words.
- No quotation marks.
- No punctuation.
- Return ONLY the title.

User Message:
{first_message}
"""

    title = await generate_response(prompt)

    print("=" * 50)

    print("GENERATED TITLE:", repr(title))

    print("=" * 50)

    return title.strip()