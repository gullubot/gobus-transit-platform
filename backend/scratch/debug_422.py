import sys
sys.path.append('.')
from fastapi.testclient import TestClient
from app.main import app
from app.db.seed import ORG_ID

client = TestClient(app)
res = client.get(f'/api/passenger/services/search?organization_id={ORG_ID}&origin_id=30000000-0000-0000-0000-000000000001&destination_id=30000000-0000-0000-0000-000000000002')
print(res.status_code)
print(res.json())
