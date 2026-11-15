# Bundled CAPTCHA recognition source

The recognition engine and glyph bank originate from yii-captcha-solver 0.1.1
in the sibling yii-captcha-test project. They are bundled inside OBIS infrastructure;
that checkout is not needed at runtime or during the application build.

`solver.solve(image_bytes, expected_hash)` returns a confident answer or `None`, and
raises `InvalidCaptchaError` for invalid challenges. It uses the existing OBIS profile
(5–6 lowercase letters, 120 × 46 pixels). `LocalCaptchaRecognizer` runs one disposable
worker process at a time. The sibling infrastructure adapter `captcha_worker.py` imports
the library only in that child process and maps invalid challenges to `None`.
Worker exit releases the glyph bank and temporary search allocations without retaining
them in the long-running bot. The bundled library itself has no process or CLI logic.

Only `_engine.py` is excluded from application lint/format rewriting and internal
type checking. Its search algorithm and confidence thresholds remain unchanged;
the unused candidate renderer was removed. The typed wrapper replaces the original
profile/result classes. CLI, HTTP acquisition, report serialization and package
metadata are omitted. Challenge acquisition and login remain owned by `ObisClient`.

`data/yii-glyphs.npz` must stay beside the engine. Yii and Spicy Rice license notices
are retained because the glyph bank derives from their renderer and font. Runtime
dependencies are the application's NumPy and Pillow dependencies. No font loading,
separate installation, labeling tools or training datasets are required.
