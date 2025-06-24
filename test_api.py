from pdf2zh import translate
from pdf2zh.doclayout import OnnxModel

model = OnnxModel.load_available()
params = {
    "model": model,
    "lang_in": "en",
    "lang_out": "zh",
    "service": "google",
    "thread": 4,
}

(file_mono, file_dual) = translate(files=["test.pdf"], **params)[0]
