# ku-cli-python
Very simple KuCoin cli. 

Create these in the KuCoin web portal and set them in your shell:

```
export KUCOIN_API_KEY=
export KUCOIN_API_SECRET=
export KUCOIN_API_PASSPHRASE=
```

## Usage

Balance overview:
```
$ python src/main.py balances
   ACCOUNT   CURRENCY         BALANCE       AVAILABLE           HOLDS
      main       USDT         77.6651         77.6651               0
     trade        XLM      27.7777854      27.7777854               0
```

Fetch ticker data:
```
$ python src/main.py ticker --symbol XLM-USDT
SYMBOL     PRICE                BIDRATE              ASKRATE
XLM-USDT   0.33666              0.336675             0.33676
```

Create a sell order:
```
$ python src/main.py create --pair XLM-USDT --spend 27.777 --direction sell --confirm
Going to buy 9.329 USDT at 0.335857 XLM, spending 27.777 XLM
> created 6139fb60351aecddd6976976
```

Listing orders:
```
$ python src/main.py orders
STATUS     DIRECTION  SYMBOL     TYPE       PRICE           QUANTITY        FEES                 CREATED                        ID
closed     sell       XLM-USDT   limit      0.335857        27.777          0.009329099889       1631189856030                  6139fb60351aecddd6976976
```

Sending a portfolio to Slack requires an `allocations.conf` file:
```
version = "1.0"
allocations = [
  {
    name = BTC
    pair = BTC-USDC
  }
]
```
And an environment variable with the webhook url: `KU_SLACK_URL=https://slack`

Sending the message to Slack:
```
python src/main.py announce
Sending message to https://hooks.slack.com/services/x/y/z
```

## Notes
Remember to whitelist withdrawals and IP access.

## Development
PyCharm terminal: `export LC_ALL=en_US.utf-8 LANG=en_US.utf-8`
