import re

def remove_think_tags(text: str) -> str:
    """Remove todo o conteúdo entre as tags <think> e </think> de um texto.

    Args:
        text: Texto de entrada possivelmente contendo tags <think>.

    Returns:
        Texto sem as tags <think> e seu conteúdo.
    """
    return re.sub(r"<think>[\s\S]*?<\/think>", "", text, flags=re.IGNORECASE) 