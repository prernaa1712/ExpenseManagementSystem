import requests


url = "http://127.0.0.1:5000/api/expenses"


expense = {

    "amount": 250,

    "category": "Food",

    "date": "2026-10-03",

    "description": "Lunch"

}


response = requests.post(
    url,
    json=expense
)


print(response.status_code)

print(response.json())