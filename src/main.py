import datetime
import logging

import click
import os
import requests
import sys

from kucoin.client import Market, User, Trade
from pyhocon import ConfigFactory


api_key = os.getenv('KUCOIN_API_KEY')
api_secret = os.getenv('KUCOIN_API_SECRET')
api_passphrase = os.getenv('KUCOIN_API_PASSPHRASE')

trade_client = Trade(api_key, api_secret, api_passphrase, is_sandbox=False)
user_client = User(api_key, api_secret, api_passphrase, is_sandbox=False)
market_client = Market()


@click.group()
def cli():
    """ Simple KuCoin cli, have fun """
    if not (api_key or api_secret or api_passphrase):
        click.secho('Make sure to configure API_KEY, API_SECRET and API_PASSPHRASE in your env', fg='red')
        sys.exit()


@cli.command('balances')
@click.option('--symbol', help='Optional symbol to view (example: USDT)')
@click.option('--boring', default=False, help='If set, only display amount available', is_flag=True)
def get_balances(symbol, boring):
    """ List all balances """
    cols = "{:>10} {:>10} {:>15} {:>15} {:>15} {:>15}"
    if not boring:
        click.secho(cols.format('ACCOUNT', 'CURRENCY', 'BALANCE', 'AVAILABLE', 'HOLDS', 'PRICE_USD'), fg='green')

    accounts = user_client.get_account_list(currency=symbol)
    accounts_sorted = sorted(accounts, key=lambda k: k['type'])

    symbols = list(map(lambda k: k['currency'], accounts_sorted))
    price_in_usd = market_client.get_fiat_price(currencies=",".join(symbols))

    for a in accounts_sorted:
        if float(a['balance']) > 0.01:
            currency = a['currency']
            price = round(float(price_in_usd[currency]) * float(a['available']), 2)
            if boring:
                click.secho("{}:{}:{}".format(a['type'], currency, a['available']))
            else:
                click.secho(cols.format(a['type'], currency, a['balance'], a['available'], a['holds'], price))


@cli.command('deposit')
@click.option('--currency', required=True, help='Currency for which to get deposit address')
def get_deposit_address(currency):
    """ Returns wallet address, memo and network for given currency """
    r = user_client.get_deposit_addressv2(currency)
    if 'code' in r:
        click.secho(f"failed with code: {r['code']}", bg='red')
    else:
        for a in r:
            click.secho(f"{a['address']} {a['memo']} {a['chain']}")


@cli.command('cancel')
@click.option('--order', required=True, help='order id to cancel')
def cancel_order(order):
    """ Cancel an order """
    try:
        r = trade_client.cancel_order(order)
        click.secho(f"Order cancelled", fg='red')
    except Exception as e:
        click.secho(f"Failed to cancel order with {e}", fg='red')


@cli.command('orders')
def get_orders():
    """ List all open and closed orders """
    cols = "{:<10} {:<10} {:<10} {:<10} {:<15} {:<15} {:<20} {:<30} {:<40}"
    click.secho(cols.format("STATUS", "DIRECTION", "SYMBOL", "TYPE", "PRICE", "QUANTITY", "FEES", "CREATED", "ID"), fg='green')

    active_orders = trade_client.get_order_list(status='active')
    closed_orders = trade_client.get_order_list()

    for o in active_orders['items'] + closed_orders['items']:
        status = 'open' if o['isActive'] else 'closed'
        created = datetime.datetime.utcfromtimestamp(o['createdAt'] / 1000).strftime('%Y-%m-%dT%H:%M:%SZ')
        click.secho(cols.format(status, o['side'], o['symbol'], o['type'], o['price'], o['size'], o['fee'], created, o['id']))


def _get_ticker_data(symbol):
    r = market_client.get_ticker(symbol)
    if 'code' in r:
        reason = r['code']
        click.secho(f'Error fetching ticker data: {reason}', fg='red')
        sys.exit()
    return r


@cli.command('ticker')
@click.option('--symbol', required=True, help='Symbol to view (example: ADA-EUR)')
def get_ticker(symbol):
    """ Get information about a ticker """
    cols = '{:<10} {:<20} {:<20} {:<20} {:<20}'
    click.secho(cols.format('SYMBOL', 'PRICE', 'BIDRATE', 'ASKRATE', 'SPREAD'), fg='green')

    r = _get_ticker_data(symbol)
    spread = int((float(r['bestAsk']) - float(r['bestBid'])) * 10000) / 10000
    click.secho(cols.format(symbol, r['price'], r['bestBid'], r['bestAsk'], spread))


def slack_announce(text):
    if 'KU_SLACK_URL' in os.environ:
        slack_url = os.getenv('KU_SLACK_URL')
    else:
        logging.error(f'Failed: missing KU_SLACK_URL in environment')
        return

    slack_data = {
        'blocks': [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(text)
            }
        }]
    }
    click.secho(f'Sending message to {slack_url}', fg='green')
    return requests.post(slack_url, json=slack_data)


@cli.command('create')
@click.option('--pair', required=True, help='Trade pair (ticker)')
@click.option('--direction', default='BUY', show_default=True, help='Buy or sell.')
@click.option('--quantity', help='Quantity to buy or sell', type=float)
@click.option('--spend', help='Spend this amount', type=float)
@click.option('--confirm', default=False, help='If not set, do not execute', is_flag=True)
@click.option('--slack', default=False, help='If set, announce to Slack', is_flag=True)
def create_order(pair, direction, quantity, spend, confirm, slack):
    """ Create a new order """
    market = _get_ticker_data(pair)

    if not spend and not quantity:
        click.secho('need one of --quantity or --spend', fg='red')
        return

    if direction.upper() == 'BUY':
        limit = float(market['bestAsk'])
        if spend:
            quantity = spend / limit
        else:
            spend = quantity / limit
        target, base = pair.split('-')
    else:
        limit = float(market['bestBid'])
        if spend:
            quantity = spend * limit
        else:
            spend = limit * quantity
        base, target = pair.split('-')

    # TODO: Seems this isn't working as expected, so let's just fix it at 4 decimals
    # details = market_client.get_currency_detail(target, chain=None)
    # precision = 4 #details['precision']
    quantity = int(quantity * 10000) / 10000

    click.secho(f'Going to buy {quantity} {target} at {limit} {base}, spending {spend} {base}', fg='green')

    # TODO: ugly, but works for now...
    if direction.upper() == 'SELL':
        quantity = spend

    if confirm:
        try:
            r = trade_client.create_limit_order(pair, direction, quantity, limit)
            if 'orderId' not in r:
                reason = r
                click.secho(f'Failed with reason: {reason}', fg='red')
            else:
                result = f"> created {r['orderId']}"
                click.secho(result, fg='red')
                if slack:
                    text = [
                        '> :tada: order created :tada:',
                        f'> :money_with_wings: buy *{quantity} {target}* at *{limit} {base}*, spending *{spend} {base}*'
                    ]
                    slack_announce(text)
        except Exception as e:
            click.secho(e, fg='red')
    else:
        click.secho('no action taken, use --confirm to create this order', fg='red')


@cli.command('transfer')
@click.option('--currency', required=True, help='Currency')
@click.option('--amount', required=True, help='Amount to transfer', type=float)
@click.option('--source', default='main', show_default=True, help='Main, trade or pool')
@click.option('--dest', default='trade', show_default=True, help='Main, trade or pool')
@click.option('--confirm', default=False, help='If not set, do not execute', is_flag=True)
def transfer(currency, amount, source, dest, confirm):
    """ Transfer funds in your account """
    click.secho(f'Going to transfer {amount} of {currency} from {source} to {dest}', fg='green')
    if confirm:
        try:
            r = user_client.inner_transfer(currency, source, dest, amount)
            result = f"> created {r['orderId']}"
            click.secho(result, fg='red')
        except Exception as e:
            click.secho(f'failed with: {e}', fg='red')
    else:
        click.secho('no action taken, use --confirm to create this order', fg='red')


@cli.command('announce')
def announce():
    try:
        conf = ConfigFactory.parse_file('allocations.conf')
    except Exception as e:
        click.secho(f'Failed to load config: {e}', fg='red')
        return

    symbols = list(map(lambda l: l['name'], conf['allocations']))
    accounts = filter(lambda l: l['currency'] in symbols, user_client.get_account_list(account_type='trade'))
    price_in_usd = market_client.get_fiat_price(currencies=",".join(symbols))
    text = ['> :ledger::rocket: portfolio balance']
    for a in accounts:
        if float(a['balance']) > 0.01:
            currency = a['currency']
            price = round(float(price_in_usd[currency]) * float(a['available']), 2)
            text.append("> :moneybag: {} *{}*: USD {}".format(a['available'], currency, price))

    _ = slack_announce(text)
    return


if __name__ == '__main__':
    cli()
