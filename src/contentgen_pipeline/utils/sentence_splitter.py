from typing import List
import spacy
import spacy.cli


def ensure_spacy_model(model_name: str = "pt_core_news_sm") -> spacy.language.Language:
    """Garante que o modelo spaCy está disponível, baixando se necessário.

    Args:
        model_name: Nome do modelo spaCy a ser carregado.

    Returns:
        Instância do modelo spaCy carregado.
    """
    try:
        return spacy.load(model_name)
    except OSError:
        spacy.cli.download(model_name)
        return spacy.load(model_name)

_nlp = ensure_spacy_model()

def split_sentences(text: str) -> List[str]:
    """Divide um texto em sentenças usando spaCy.

    Args:
        text: Texto de entrada.

    Returns:
        Lista de sentenças extraídas do texto.
    """
    doc = _nlp(text)
    return [sent.text.strip() for sent in doc.sents] 