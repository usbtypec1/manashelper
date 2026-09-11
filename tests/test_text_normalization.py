from manashelper.services.text_normalization import fold_turkish


def test_fold_turkish_maps_diacritics_to_latin() -> None:
    assert fold_turkish("Yazılım Mühendisliğine Giriş") == "yazilim muhendisligine giris"


def test_fold_turkish_handles_capital_dotted_i() -> None:
    assert fold_turkish("İngilizce") == "ingilizce"


def test_fold_turkish_folds_comma_below_s_variant() -> None:
    assert fold_turkish("Ș ș") == "s s"


def test_fold_turkish_is_case_insensitive_for_plain_latin() -> None:
    assert fold_turkish("Matematik") == "matematik"
