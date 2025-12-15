import os, sys, json
sys.path.insert(0, r'd:\Python\Projects\Test\Gemini\ImageGen')
out = {}
try:
    from google import genai
    out['genai_version'] = getattr(genai, '__version__', 'unknown')
except Exception as e:
    out['genai_import_error'] = repr(e)

try:
    client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
    out['client_dir'] = [n for n in dir(client) if not n.startswith('_')]
    try:
        out['client_models_dir'] = [n for n in dir(client.models) if not n.startswith('_')]
    except Exception as e:
        out['client_models_error'] = repr(e)
    try:
        out['client_chats_dir'] = [n for n in dir(client.chats) if not n.startswith('_')]
    except Exception as e:
        out['client_chats_error'] = repr(e)
except Exception as e:
    out['client_init_error'] = repr(e)

print(json.dumps(out, indent=2))
