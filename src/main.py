import click
import os
import sys
from kucoin.client import Market, User, Trade


api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')
api_passphrase = os.getenv('API_PASSPHRASE')

trade_client = Trade(api_key, api_secret, api_passphrase, is_sandbox=False)
user_client = User(api_key, api_secret, api_passphrase, is_sandbox=False)
market_client = Market()


@click.group()
def cli():
    """ Simple KuCoin cli, have fun """


@cli.command('balances')
def get_balances():
    """ List all balances """
    accounts = user_client.get_account_list()

    cols = "{:>10} {:>10} {:>15} {:>15} {:>15}"
    click.secho(cols.format('ACCOUNT', 'CURRENCY', 'BALANCE', 'AVAILABLE', 'HOLDS'), fg='green')

    for a in accounts:
        if float(a['balance']) > 0.0005:
            click.secho(cols.format(a['type'], a['currency'], a['balance'], a['available'], a['holds']))


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


@cli.command('orders')
def get_orders():
    """ List all open and closed orders """
    cols = "{:<10} {:<10} {:<10} {:<10} {:<15} {:<15} {:<20} {:<30}"
    click.secho(cols.format("STATUS", "DIRECTION", "SYMBOL", "TYPE", "PRICE", "QUANTITY", "FEES", "CREATED"), fg='green')

    r = trade_client.get_order_list()
    for o in r['items']:
        status = 'open' if o['isActive'] else 'closed'
        # TODO: pretify
        created = o['createdAt']
        click.secho(cols.format(status, o['side'], o['symbol'], o['type'], o['price'], o['size'], o['fee'], created))


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
    cols = '{:<10} {:<20} {:<20} {:<20}'
    click.secho(cols.format('SYMBOL', 'PRICE', 'BIDRATE', 'ASKRATE'), fg='green')

    r = _get_ticker_data(symbol)
    click.secho(cols.format(symbol, r['price'], r['bestBid'], r['bestAsk']))


@cli.command('create')
@click.option('--pair', required=True, help='Trade pair (ticker)')
@click.option('--direction', default='BUY', show_default=True, help='Buy or sell.')
@click.option('--quantity', help='Quantity to buy or sell', type=float)
@click.option('--spend', help='Spend this amount', type=float)
@click.option('--confirm', default=False, help='If not set, do not execute', is_flag=True)
def create_order(pair, direction, quantity, spend, confirm):
    """ Create a new order """
    market = _get_ticker_data(pair)
    limit = float(market['bestAsk'])

    if not spend and not quantity:
        click.secho('need one of --quantity or --spend', fg='red')
        return

    if spend:
        quantity = spend / limit
    target, base = pair.split('-')
    spend = limit * quantity
    click.secho(f'Going to {direction.lower()} {quantity} {target} at {limit} {base}, spending {spend} {base}', fg='green')

    if confirm:
        try:
            r = trade_client.create_limit_order(pair, direction, quantity, limit)
            if 'orderId' not in r:
                reason = r
                click.secho(f'Failed with reason: {reason}', fg='red')
            else:
                result = f"> created {r['orderId']}"
                click.secho(result, fg='red')
        except Exception as e:
            click.secho(e, fg='red')
    else:
        click.secho('no action taken, use --confirm to create this order', fg='red')


if __name__ == '__main__':
    cli()
