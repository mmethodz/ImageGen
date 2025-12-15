import os, sys
sys.path.insert(0, r'd:\Python\Projects\Test\Gemini\ImageGen')
from google import genai
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
print('Listing models via client.models.list()')
try:
    for m in client.models.list():
        name = getattr(m, 'name', None) or getattr(m, 'model', None) or str(m)
        print('-', name)
except Exception as e:
    print('client.models.list() failed:', repr(e))
