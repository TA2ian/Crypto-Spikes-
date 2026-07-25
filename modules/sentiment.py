import requests

def get_fear_and_greed_index() -> dict:
    """جلب مؤشر الخوف والجشع"""
    url = "https://api.alternative.me/fng/"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        val = int(data['data'][0]['value'])
        status = data['data'][0]['value_classification']
        return {"value": val, "status": status}
    except Exception:
        return {"value": 50, "status": "Neutral"}
