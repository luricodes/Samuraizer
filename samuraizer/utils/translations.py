# samuraizer/gui/widgets/configuration/repository/github/utils/translations.py

import logging
import os
import re
from PyQt6.QtCore import QTranslator, QLocale, QObject

logger = logging.getLogger(__name__)

class TranslationManager(QObject):
    """Manages application translations for localization and internationalization."""

    def __init__(self, app, translations_path: str = "translations"):
        """
        Initialize the TranslationManager.

        Args:
            app: The main application instance.
            translations_path (str): Path to the translation files.
        """
        super().__init__()
        self.app = app
        self.translator = QTranslator()
        self.current_locale = QLocale.system()
        self.translations_path = translations_path
        self.supported_locales = self._load_supported_locales()
        self.load_translation(self.current_locale)

    def _load_supported_locales(self) -> list:
        """
        Load supported locales based on available translation files.

        Returns:
            list: A list of supported locale names.
        """
        import os
        locales = []
        try:
            for file in os.listdir(self.translations_path):
                match = re.match(r'samuraizer_gui_(?P<locale>\w+)\.qm', file)
                if match:
                    locales.append(match.group('locale'))
            logger.debug(f"Supported locales loaded: {locales}")
        except FileNotFoundError:
            logger.warning(f"Translations directory '{self.translations_path}' not found.")
        except Exception as e:
            logger.error(f"Error loading supported locales: {e}")
        return locales

    def load_translation(self, locale: QLocale):
        """
        Load the translation file based on the selected locale.

        Args:
            locale (QLocale): The locale to load.
        """
        translation_file = os.path.join(
            self.translations_path, f"samuraizer_gui_{locale.name()}.qm"
        )
        if self.translator.load(translation_file):
            self.app.installTranslator(self.translator)
            self.current_locale = locale
            logger.info(f"Loaded translation for locale: {locale.name()}")
        else:
            logger.warning(f"No translation file found for locale: {locale.name()}")
            # Fallback to default language if available
            if locale.name() != "en_US":
                fallback_locale = QLocale("en_US")
                fallback_file = os.path.join(
                    self.translations_path, f"samuraizer_gui_{fallback_locale.name()}.qm"
                )
                if self.translator.load(fallback_file):
                    self.app.installTranslator(self.translator)
                    self.current_locale = fallback_locale
                    logger.info(f"Fallback to default locale: {fallback_locale.name()}")
                else:
                    logger.error("Default translation file not found. Application will run without translations.")

    def switch_language(self, locale_name: str):
        """
        Switch the application language at runtime.

        Args:
            locale_name (str): The name of the locale to switch to.
        """
        if locale_name not in self.supported_locales:
            logger.error(f"Attempted to switch to unsupported locale: {locale_name}")
            return

        self.app.removeTranslator(self.translator)
        new_translator = QTranslator()
        translation_file = os.path.join(
            self.translations_path, f"samuraizer_gui_{locale_name}.qm"
        )
        if new_translator.load(translation_file):
            self.app.installTranslator(new_translator)
            self.translator = new_translator
            self.current_locale = QLocale(locale_name)
            logger.info(f"Switched to language: {locale_name}")
            self._refresh_ui()
        else:
            logger.error(f"Translation file for locale '{locale_name}' not found.")
            # Reinstall previous translator to maintain consistency
            if self.translator.load(os.path.join(
                self.translations_path, f"samuraizer_gui_{self.current_locale.name()}.qm"
            )):
                self.app.installTranslator(self.translator)
                logger.info(f"Reinstalled previous locale: {self.current_locale.name()}")
            else:
                logger.error("Reinstalling previous locale failed.")

    def _refresh_ui(self):
        """
        Refresh the UI components to apply the new translations.
        """
        # This method should emit signals or call methods to refresh UI components.
        # Implementation depends on the overall application structure.
        logger.debug("UI refresh initiated to apply new translations.")
        for widget in self.app.allWidgets():
            widget.retranslateUi()

    def get_available_locales(self) -> list:
        """
        Get a list of available locales based on translation files.

        Returns:
            list: A list of available locale names.
        """
        return self.supported_locales
