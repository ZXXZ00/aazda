import threading
import re
from symspellpy import SymSpell, Verbosity
import spelling_db

class SpellingService:
    def __init__(self):
        self.sym_spell = SymSpell(max_dictionary_edit_distance=3, prefix_length=7)
        self._lock = threading.Lock()
        self._is_loaded = False

    def load_if_needed(self):
        """Lazy load the vocabulary from SQLite into SymSpell if not already loaded."""
        if self._is_loaded:
            return
        with self._lock:
            if self._is_loaded:
                return
            self._load_from_db_unlocked()
            self._is_loaded = True

    def _load_from_db_unlocked(self):
        """Loads all vocabulary into a fresh SymSpell instance. Assumes lock is held."""
        new_sym_spell = SymSpell(max_dictionary_edit_distance=3, prefix_length=7)
        vocab = spelling_db.get_all_vocabulary()
        for word, freq in vocab.items():
            new_sym_spell.create_dictionary_entry(word, freq)
        self.sym_spell = new_sym_spell

    def correct_query(self, query: str) -> str:
        """
        Corrects spelling errors in the user query.
        Preserves non-alphanumeric prefixes/suffixes (like parentheses/punctuation)
        and attempts to match capitalization of the original query terms.
        """
        self.load_if_needed()
        if not query.strip():
            return query

        words = query.split()
        corrected_words = []
        for word in words:
            # Split into: prefix (non-alphanumeric), core word, suffix (non-alphanumeric)
            match = re.match(r"^([^a-zA-Z0-9]*)(.*?)([^a-zA-Z0-9]*)$", word)
            if match:
                prefix, clean_word, suffix = match.groups()
            else:
                prefix, clean_word, suffix = "", word, ""

            # Only correct purely alphabetic words
            if not clean_word or not clean_word.isalpha():
                corrected_words.append(word)
                continue

            clean_word_lower = clean_word.lower()
            word_len = len(clean_word_lower)
            if word_len <= 4:
                max_ed = 1
            elif word_len <= 8:
                max_ed = 2
            else:
                max_ed = 3

            with self._lock:
                suggestions = self.sym_spell.lookup(
                    clean_word_lower, Verbosity.CLOSEST, max_edit_distance=max_ed
                )

            if suggestions:
                suggested_term = suggestions[0].term
                # Match the casing pattern of the original word
                if clean_word.isupper():
                    suggested_term = suggested_term.upper()
                elif clean_word[0].isupper():
                    suggested_term = suggested_term.capitalize()
                corrected_words.append(f"{prefix}{suggested_term}{suffix}")
            else:
                corrected_words.append(word)

        return " ".join(corrected_words)

    def update_vocab(self, updates: dict[str, int]):
        """
        Dynamically updates the in-memory SymSpell instance.
        If a word's count is <= 0 (deleted), performs an atomic rebuild from the SQLite
        database to clean up delete paths and avoid KeyError inside symspellpy.
        """
        if not updates:
            return
        self.load_if_needed()
        with self._lock:
            if any(freq <= 0 for freq in updates.values()):
                # Rebuild to clean up delete structures
                self._load_from_db_unlocked()
            else:
                # Fast incremental update
                for word, freq in updates.items():
                    self.sym_spell.create_dictionary_entry(word, freq)

# Global thread-safe singleton
spelling_service = SpellingService()
