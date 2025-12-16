# SonChangGi.github.io

## NASDAQ 수익률 분석 스크립트

`scripts/nasdaq_returns.py` 스크립트는 야후 파이낸스 데이터를 이용해 미국 나스닥 종합지수(`^IXIC`)의 2005-01-01부터 2025-10-28까지의 수익률을 계산하고 시각화합니다.

`scripts/trading_environment.py` 스크립트는 미국 개별주/ETF를 대상으로 중기 팩터(모멘텀, 변동성, 평균 달러 거래대금)로 유니버스를 선별하고, 최근 intraday 데이터에서 ORB/VWAP 기반 진입만 수행하는 단기 트레이딩 환경을 시뮬레이션합니다.

### 의존성 설치

두 스크립트 모두 `yfinance`, `pandas`, `numpy`, `matplotlib` 등이 필요합니다. 아래와 같이 설치할 수 있습니다.

```bash
pip install yfinance pandas numpy matplotlib
```

### ORB/VWAP 트레이딩 환경 실행 예시

최근 60일 이내 intraday 데이터가 제공되는 미국 주식/ETF에 대해 사용할 수 있으며, 기본 유니버스는 대형주와 주요 ETF로 구성됩니다.

```bash
python scripts/trading_environment.py --tickers AAPL MSFT NVDA SPY QQQ \
  --start-date 2024-12-15 --end-date 2025-01-31 --interval 5m --top-n 5 \
  --min-dollar-volume 5000000 --risk-per-trade 0.01
```

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
