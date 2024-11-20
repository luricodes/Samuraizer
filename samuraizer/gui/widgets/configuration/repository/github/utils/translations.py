# samuraizer/gui/widgets/configuration/repository/github/utils/translations.py

from PyQt6.QtCore import QTranslator, QLocale, QObject

class TranslationManager(QObject):
    """Manages application translations for localization and internationalization."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.translator = QTranslator()
        self.load_translation(QLocale.system())

    def load_translation(self, locale: QLocale):
        """Load the translation file based on the selected locale."""
        translation_file = f"samuraizer_gui_{locale.name()}.qm"
        if self.translator.load(translation_file):
            self.app.installTranslator(self.translator)
            print(f"Loaded translation for locale: {locale.name()}")
        else:
            print(f"No translation file found for locale: {locale.name()}")

    def switch_language(self, locale_name: str):
        """Switch the application language at runtime."""
        self.app.removeTranslator(self.translator)
        new_translator = QTranslator()
        translation_file = f"samuraizer_gui_{locale_name}.qm"
        if new_translator.load(translation_file):
            self.app.installTranslator(new_translator)
            self.translator = new_translator
            print(f"Switched to language: {locale_name}")
        else:
            print(f"Translation file for language '{locale_name}' not found.")
