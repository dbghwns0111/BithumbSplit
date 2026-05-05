import requests
import json
import csv

# 빗썸 API 요청 URL
url = "https://api.bithumb.com/v1/market/all?isDetails=false"
headers = {"accept": "application/json"}

# API GET 요청
response = requests.get(url, headers=headers)

# JSON 데이터 파싱
data = response.json()

# 보기 좋게 정리된 JSON 문자열 생성
pretty_json = json.dumps(data, indent=2, ensure_ascii=False)

# 텍스트 파일로 저장
with open("bithumb_markets.txt", "w", encoding="utf-8") as f:
    f.write(pretty_json)

print("bithumb_markets.txt 파일로 저장 완료")

# 텍스트 파일에서 JSON 읽기
with open("bithumb_markets.txt", "r", encoding="utf-8") as f:
    json_data = json.load(f)  # JSON 문자열을 파이썬 객체로 파싱

# CSV 파일로 저장
with open("bithumb_markets.csv", "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["market", "korean_name", "english_name"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()  # CSV 헤더 작성
    writer.writerows(json_data)  # JSON 데이터를 행 단위로 작성

print("bithumb_markets.csv 파일로 저장 완료")