from gestia.prediction import LEARN_THRESHOLD, MAX_VOCABULARY, WordPredictor, fold


def test_first_letters_give_spanish_suggestions() -> None:
    predictor = WordPredictor()
    suggestions = predictor.suggest("gra")
    assert "gracias" in suggestions
    assert all(fold(word).startswith("gra") for word in suggestions)
    assert len(predictor.suggest("p", limit=3)) == 3


def test_accents_and_case_are_respected() -> None:
    predictor = WordPredictor()
    assert "miércoles" in predictor.suggest("mie", limit=10)
    assert "está" in predictor.suggest("esta", limit=10)
    assert "esta" not in predictor.suggest("esta", limit=10)  # Ya está escrita.
    assert "Gracias" in predictor.suggest("Gra")
    assert "GRACIAS" in predictor.suggest("GRA")
    assert fold("Año") == "año"


def test_new_word_is_suggested_after_writing_it_several_times() -> None:
    vocabulary: dict[str, int] = {}
    predictor = WordPredictor(vocabulary)
    assert "gestia" not in predictor.suggest("ges", limit=10)
    for _ in range(LEARN_THRESHOLD - 1):
        predictor.learn("GestIA")
    assert "gestia" not in predictor.suggest("ges", limit=10)
    predictor.learn("gestia")
    assert predictor.suggest("ges")[0] == "gestia"
    assert vocabulary == {"gestia": LEARN_THRESHOLD}


def test_only_plain_words_are_learned_and_vocabulary_is_bounded() -> None:
    predictor = WordPredictor()
    assert not predictor.learn("a")
    assert not predictor.learn("1234")
    assert not predictor.learn("hola!")
    for index in range(MAX_VOCABULARY + 5):
        predictor.learn("palabra" + "".join(chr(97 + int(d)) for d in str(index)))
    assert len(predictor.vocabulary) == MAX_VOCABULARY
    predictor.learn("ultima")
    assert "ultima" in predictor.vocabulary
    predictor.forget()
    assert predictor.vocabulary == {}
