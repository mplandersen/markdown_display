# ML Model Setup Instructions

This repository contains a complete ML-powered PII detection system, but the large model files are not included in Git due to size constraints.

## Quick Setup

Run the model preparation script to download and convert the required models:

```bash
python3 scripts/prepare_model.py
```

This will:
1. Download the `dslim/bert-base-NER` model from Hugging Face
2. Convert it to ONNX format for browser compatibility
3. Create the necessary tokenizer configuration files
4. Place everything in `static/models/` directory

## Model Details

- **Base Model**: `dslim/bert-base-NER` (BERT-based Named Entity Recognition)
- **Format**: ONNX (optimized for web deployment)
- **Size**: ~104MB (excluded from Git)
- **Performance**: Expected 95-96% F1 score on PII detection

## Files Generated

After running `scripts/prepare_model.py`, you'll have:
- `static/models/distilbert-ner-quantized.onnx` - Main model file
- `static/models/wasm_config.json` - Browser tokenizer config
- `.cache/huggingface/` - Model cache (also excluded from Git)

## Validation

Run the validation script to test the model:

```bash
python3 scripts/validate_model.py
```

## Testing

Run the comprehensive test suite:

```bash
python3 scripts/pii_test_suite.py
```

This will generate a detailed test report showing the model's performance on various PII types.

## Running the Application

After setting up the models:

```bash
python3 app.py
```

The application will be available at `http://localhost:5000` with full ML-powered PII detection capabilities. 