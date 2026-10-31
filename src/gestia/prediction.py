"""Predicción de palabras en español con aprendizaje local (HU-20).

Las sugerencias combinan un diccionario de frecuencias incluido (``lexicon_es``) con las
palabras que la persona escribe. Lo aprendido son solo palabras sueltas y su conteo, se guarda
en el perfil y puede borrarse; nunca frases ni texto completo.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, MutableMapping

from gestia.lexicon_es import WORDS

# Una palabra nueva se sugiere a partir de la segunda vez que se escribe.
LEARN_THRESHOLD = 2
MAX_VOCABULARY = 2000
MAX_WORD_LENGTH = 40


def fold(text: str) -> str:
    """Minúsculas y sin tildes, para que «esta» encuentre «está» (la ñ se conserva)."""
    decomposed = unicodedata.normalize("NFD", text.casefold().replace("ñ", "\0"))
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return unicodedata.normalize("NFC", plain).replace("\0", "ñ")


def is_word(text: str) -> bool:
    return 2 <= len(text) <= MAX_WORD_LENGTH and text.isalpha()


def match_case(word: str, typed: str) -> str:
    """Respeta las mayúsculas que ya escribió la persona."""
    if len(typed) > 1 and typed.isupper():
        return word.upper()
    if typed[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


class WordPredictor:
    def __init__(
        self,
        vocabulary: MutableMapping[str, int] | None = None,
        base: Iterable[str] = WORDS,
    ) -> None:
        # ``vocabulary`` suele ser el diccionario del perfil: aprender lo modifica en sitio.
        self.vocabulary: MutableMapping[str, int] = {} if vocabulary is None else vocabulary
        self._base = list(dict.fromkeys(word.casefold() for word in base))

    def suggest(self, prefix: str, limit: int = 3) -> list[str]:
        if not prefix or not prefix.isalpha():
            return []
        key = fold(prefix)
        learned = sorted(
            (
                (count, word)
                for word, count in self.vocabulary.items()
                if count >= LEARN_THRESHOLD and fold(word).startswith(key)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        candidates = [word for _, word in learned]
        candidates += [word for word in self._base if fold(word).startswith(key)]
        typed = prefix.casefold()
        result: list[str] = []
        for word in dict.fromkeys(candidates):
            if word == typed:
                continue  # No hay nada que completar.
            result.append(match_case(word, prefix))
            if len(result) == limit:
                break
        return result

    def learn(self, word: str) -> bool:
        """Cuenta una palabra escrita. Devuelve ``True`` si el vocabulario cambió."""
        if not is_word(word):
            return False
        word = word.casefold()
        self.vocabulary[word] = self.vocabulary.get(word, 0) + 1
        if len(self.vocabulary) > MAX_VOCABULARY:
            # Se descarta la menos usada, nunca la recién escrita.
            rarest = min(
                (item for item in self.vocabulary if item != word),
                key=lambda item: self.vocabulary[item],
            )
            del self.vocabulary[rarest]
        return True

    def forget(self) -> None:
        self.vocabulary.clear()
