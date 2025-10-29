# SonChangGi.github.io

## NASDAQ 수익률 분석 스크립트

`scripts/nasdaq_returns.py` 스크립트는 야후 파이낸스 데이터를 이용해 미국 나스닥 종합지수(`^IXIC`)의 2005-01-01부터 2025-10-28까지의 수익률을 계산하고 시각화합니다.

### 사용 방법

```bash
pip install matplotlib pandas yfinance
python scripts/nasdaq_returns.py
```

필요에 따라 티커나 기간을 다음과 같이 변경할 수 있습니다.

```bash
python scripts/nasdaq_returns.py --ticker ^NDX --start-date 2010-01-01 --end-date 2025-10-28
```

스크립트는 기간 동안의 일별 수익률과 누적 수익률을 계산하여 요약 정보를 출력하고, 가격과 누적 수익률을 시각화한 그래프를 생성합니다.
